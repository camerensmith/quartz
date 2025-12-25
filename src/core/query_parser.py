"""Search query parser using lark for field predicates and boolean logic"""

from typing import List, Dict, Optional, Any

from lark import Lark, Transformer, Token
from lark.exceptions import LarkError

# Query grammar for lark
QUERY_GRAMMAR = """
start: expression

expression: orexpr

orexpr: andexpr (OR andexpr)*

andexpr: term (AND term)*

term: predicate | "(" expression ")" | NOT term

predicate: fieldpredicate | textpredicate

fieldpredicate: FIELDNAME ":" value | FIELDNAME OP value

textpredicate: TEXT

value: quotedstring | unquotedstring | number

quotedstring: "\\"" STRING "\\"" | "'" STRING "'"

unquotedstring: STRING

number: NUMBER

FIELDNAME: /[a-zA-Z][a-zA-Z0-9]*/
OP: ">" | "<" | ">=" | "<=" | "=" | "!="
STRING: /[^"']+/
TEXT: /[^\\s:()]+/
NUMBER: /-?\\d+(\\.\\d+)?/

OR: /\\bor\\b/i
AND: /\\band\\b/i
NOT: /\\bnot\\b/i

%import common.WS
%ignore WS
"""


class QueryTransformer(Transformer):
    """Transform parsed query tree into filter conditions"""
    
    def __init__(self, available_fields: List[str]):
        super().__init__()
        self.available_fields = {f.lower() for f in available_fields}
    
    def start(self, args):
        return args[0]
    
    def orexpr(self, args):
        if len(args) == 1:
            return args[0]
        return {"op": "OR", "args": args}
    
    def andexpr(self, args):
        if len(args) == 1:
            return args[0]
        return {"op": "AND", "args": args}
    
    def term(self, args):
        if len(args) == 1:
            return args[0]
        # NOT term
        return {"op": "NOT", "args": [args[0]]}
    
    def predicate(self, args):
        return args[0]
    
    def fieldpredicate(self, args):
        if len(args) == 2:
            # field:value or field=value
            field_name = str(args[0]).lower()
            value = args[1]
            return {"type": "field", "field": field_name, "op": "=", "value": value}
        else:
            # field>value, field<value, etc.
            field_name = str(args[0]).lower()
            op = str(args[1])
            value = args[2]
            return {"type": "field", "field": field_name, "op": op, "value": value}
    
    def textpredicate(self, args):
        # Simple text search (FTS)
        return {"type": "text", "value": str(args[0])}
    
    def quotedstring(self, args):
        return str(args[0])
    
    def unquotedstring(self, args):
        return str(args[0])
    
    def number(self, args):
        try:
            return float(args[0])
        except ValueError:
            return str(args[0])


class QueryParser:
    """Parse and execute search queries"""
    
    def __init__(self, available_fields: List[str]):
        self.parser = Lark(QUERY_GRAMMAR, start='start', parser='lalr')
        self.available_fields = available_fields
    
    def parse(self, query: str) -> Optional[Dict[str, Any]]:
        """Parse a query string into a filter tree"""
        if not query or not query.strip():
            return None
        
        query = query.strip()
        
        # If query doesn't contain field syntax, treat as simple text search
        if ":" not in query and not any(op in query for op in [">", "<", "=", "!"]):
            return {"type": "text", "value": query}
        
        try:
            tree = self.parser.parse(query)
            transformer = QueryTransformer(self.available_fields)
            return transformer.transform(tree)
        except LarkError as e:
            # Return simple text search on parse error
            return {"type": "text", "value": query}
    
    def _format_fts5_query(self, query: str) -> str:
        """Format query string for FTS5 search with proper escaping and prefix matching"""
        if not query:
            return ""
        
        query = query.strip()
        
        # If query contains FTS5 operators (AND, OR, NOT) as part of the text (not operators),
        # we need to quote the entire phrase. Otherwise, use prefix matching.
        # Check if query looks like it might contain operators
        has_operators = any(op in query.upper() for op in [' AND ', ' OR ', ' NOT '])
        
        if has_operators and len(query.split()) > 1:
            # Quote the entire phrase to treat operators as literal text
            escaped = query.replace('"', '""')
            return f'"{escaped}"*'
        
        # For simple queries, use prefix matching per word
        words = query.split()
        formatted_words = []
        
        for word in words:
            # Escape quotes
            escaped_word = word.replace('"', '""')
            # Add * for prefix matching if the word doesn't already end with *
            if not escaped_word.endswith('*'):
                escaped_word += '*'
            formatted_words.append(escaped_word)
        
        # For single word, just return it with *
        if len(formatted_words) == 1:
            return formatted_words[0]
        
        # For multiple words, use AND (both must match) for better results
        return ' AND '.join(formatted_words)
    
    def build_sql_filter(self, filter_tree: Dict[str, Any], table_alias: str = "r") -> tuple[str, List[Any]]:
        """Build SQL WHERE clause from filter tree"""
        if not filter_tree:
            return "", []
        
        if filter_tree.get("type") == "text":
            # For now, return None to force fallback to simple_search
            # This ensures basic search works reliably
            # TODO: Fix FTS5 query formatting and re-enable
            return None, []
        
        if filter_tree.get("type") == "field":
            # Field predicate
            field = filter_tree["field"]
            op = filter_tree["op"]
            value = filter_tree["value"]
            
            # Validate field exists
            if field not in [f.lower() for f in self.available_fields]:
                # Field doesn't exist, return no results
                return "1=0", []
            
            # Build condition
            if op == "=":
                return f"{table_alias}.{field} = ?", [str(value)]
            elif op == "!=":
                return f"{table_alias}.{field} != ?", [str(value)]
            elif op == ">":
                return f"{table_alias}.{field} > ?", [str(value)]
            elif op == "<":
                return f"{table_alias}.{field} < ?", [str(value)]
            elif op == ">=":
                return f"{table_alias}.{field} >= ?", [str(value)]
            elif op == "<=":
                return f"{table_alias}.{field} <= ?", [str(value)]
        
        # Boolean operators
        if filter_tree.get("op") == "OR":
            conditions = []
            params = []
            for arg in filter_tree["args"]:
                cond, parms = self.build_sql_filter(arg, table_alias)
                if cond:
                    conditions.append(f"({cond})")
                    params.extend(parms)
            if conditions:
                return " OR ".join(conditions), params
            return "", []
        
        elif filter_tree.get("op") == "AND":
            conditions = []
            params = []
            for arg in filter_tree["args"]:
                cond, parms = self.build_sql_filter(arg, table_alias)
                if cond:
                    conditions.append(f"({cond})")
                    params.extend(parms)
            if conditions:
                return " AND ".join(conditions), params
            return "", []
        
        elif filter_tree.get("op") == "NOT":
            cond, params = self.build_sql_filter(filter_tree["args"][0], table_alias)
            if cond:
                return f"NOT ({cond})", params
            return "", []
        
        return "", []

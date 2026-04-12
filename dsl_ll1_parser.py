from collections import defaultdict


class LL1Parser:
    def __init__(self):
        self.start_symbol = "Program"
        self.table = defaultdict(dict)
        self.nonterminals = {
            "Program", "AgentList", "Agent", "AgentStmtList", "AgentStmt",
            "ToolStmt", "Task", "TaskStmtList", "ActionStmt", "ParamList",
            "ParamList'", "TaskReturnDecl", "System", "SystemStmtList",
            "SystemStmt", "VarStmt", "AssgnStmt", "IfStmt", "ForStmt",
            "RunStmt", "ArgumentList", "ArgumentList'", "Type", "Expr",
            "Expr'", "Term", "Term'", "Factor", "CompOp", "Condition",
            "OrCondition'", "AndCondition", "AndCondition'",
            "RelationalCondition", "Value", "StrValue", "BoolValue",
            "ListValue", "ValueList", "ValueList'"
        }
        self._build_table()

    def _add(self, nonterminal, lookaheads, production):
        for la in lookaheads:
            if la in self.table[nonterminal]:
                old = self.table[nonterminal][la]
                if old != production:
                    raise ValueError(
                        f"LL(1) conflict at M[{nonterminal}, {la}]: "
                        f"{old} vs {production}"
                    )
            self.table[nonterminal][la] = production

    # Antonio: here, we implement the private build_table function, that builds the table entry by entry,
    # following the algorithm from class.
    def _build_table(self):
        type_first = ["string", "int", "bool", "list"]
        value_first = ["(", "id", "num", "str", "true", "false", "[", "run"]
        system_stmt_first = ["string", "int", "bool", "list", "id", "if", "for"]

        expr_follow = [
            "==", "!=", ">=", "<=", ">", "<",
            "and", "or",
            ")", ",", "]",
            "{", "}",
            "string", "int", "bool", "list", "id", "if", "for",
            "$"
        ]
        term_follow = ["+", "-"] + expr_follow

        # Program
        self._add("Program", ["agent", "system"], ["AgentList", "System"])

        # AgentList
        self._add("AgentList", ["agent"], ["Agent", "AgentList"])
        self._add("AgentList", ["system"], ["ε"])

        # Agent
        self._add("Agent", ["agent"], ["agent", "id", "{", "AgentStmtList", "}"])

        # AgentStmtList
        self._add("AgentStmtList", ["tool", "task"], ["AgentStmt", "AgentStmtList"])
        self._add("AgentStmtList", ["}"], ["ε"])

        # AgentStmt
        self._add("AgentStmt", ["tool"], ["ToolStmt"])
        self._add("AgentStmt", ["task"], ["Task"])

        # ToolStmt
        self._add("ToolStmt", ["tool"], ["tool", "id"])

        # Task
        self._add(
            "Task",
            ["task"],
            ["task", "id", "(", "ParamList", ")", "TaskReturnDecl", "{", "TaskStmtList", "}"]
        )

        # TaskStmtList
        self._add("TaskStmtList", ["action"], ["ActionStmt", "TaskStmtList"])
        self._add("TaskStmtList", ["}"], ["ε"])

        # ActionStmt
        self._add("ActionStmt", ["action"], ["action", ":", "id", "(", "ArgumentList", ")"])

        # ParamList
        self._add("ParamList", type_first, ["Type", "id", "ParamList'"])
        self._add("ParamList", [")"], ["ε"])

        # ParamList'
        self._add("ParamList'", [","], [",", "Type", "id", "ParamList'"])
        self._add("ParamList'", [")"], ["ε"])

        # TaskReturnDecl
        self._add("TaskReturnDecl", ["->"], ["->", "Type", "id"])
        self._add("TaskReturnDecl", ["{"], ["ε"])

        # System
        self._add("System", ["system"], ["system", "{", "SystemStmtList", "}"])

        # SystemStmtList
        self._add("SystemStmtList", system_stmt_first, ["SystemStmt", "SystemStmtList"])
        self._add("SystemStmtList", ["}"], ["ε"])

        # SystemStmt
        self._add("SystemStmt", type_first, ["VarStmt"])
        self._add("SystemStmt", ["id"], ["AssgnStmt"])
        self._add("SystemStmt", ["if"], ["IfStmt"])
        self._add("SystemStmt", ["for"], ["ForStmt"])

        # VarStmt
        self._add("VarStmt", type_first, ["Type", "id", "=", "Value"])

        # AssgnStmt
        self._add("AssgnStmt", ["id"], ["id", "=", "Value"])

        # IfStmt
        self._add("IfStmt", ["if"], ["if", "Condition", "{", "SystemStmtList", "}"])

        # ForStmt
        self._add("ForStmt", ["for"], ["for", "id", "in", "id", "{", "SystemStmtList", "}"])

        # RunStmt
        self._add("RunStmt", ["run"], ["run", "id", ".", "id", "(", "ArgumentList", ")"])

        # ArgumentList
        self._add("ArgumentList", value_first, ["Value", "ArgumentList'"])
        self._add("ArgumentList", [")"], ["ε"])

        # ArgumentList'
        self._add("ArgumentList'", [","], [",", "Value", "ArgumentList'"])
        self._add("ArgumentList'", [")"], ["ε"])

        # Type
        self._add("Type", ["string"], ["string"])
        self._add("Type", ["int"], ["int"])
        self._add("Type", ["bool"], ["bool"])
        self._add("Type", ["list"], ["list"])

        # Expr
        self._add("Expr", ["(", "id", "num"], ["Term", "Expr'"])

        # Expr'
        self._add("Expr'", ["+"], ["+", "Term", "Expr'"])
        self._add("Expr'", ["-"], ["-", "Term", "Expr'"])
        self._add("Expr'", expr_follow, ["ε"])

        # Term
        self._add("Term", ["(", "id", "num"], ["Factor", "Term'"])

        # Term'
        self._add("Term'", ["*"], ["*", "Factor", "Term'"])
        self._add("Term'", ["/"], ["/", "Factor", "Term'"])
        self._add("Term'", term_follow, ["ε"])

        # Factor
        self._add("Factor", ["("], ["(", "Expr", ")"])
        self._add("Factor", ["id"], ["id"])
        self._add("Factor", ["num"], ["num"])

        # CompOp
        self._add("CompOp", ["=="], ["=="])
        self._add("CompOp", ["!="], ["!="])
        self._add("CompOp", [">="], [">="])
        self._add("CompOp", ["<="], ["<="])
        self._add("CompOp", [">"], [">"])
        self._add("CompOp", ["<"], ["<"])

        # Condition
        self._add("Condition", value_first, ["AndCondition", "OrCondition'"])

        # OrCondition'
        self._add("OrCondition'", ["or"], ["or", "AndCondition", "OrCondition'"])
        self._add("OrCondition'", ["{"], ["ε"])

        # AndCondition
        self._add("AndCondition", value_first, ["RelationalCondition", "AndCondition'"])

        # AndCondition'
        self._add("AndCondition'", ["and"], ["and", "RelationalCondition", "AndCondition'"])
        self._add("AndCondition'", ["or", "{"], ["ε"])

        # RelationalCondition
        self._add("RelationalCondition", value_first, ["Value", "CompOp", "Value"])

        # Value
        self._add("Value", ["(", "id", "num"], ["Expr"])
        self._add("Value", ["str"], ["StrValue"])
        self._add("Value", ["true", "false"], ["BoolValue"])
        self._add("Value", ["["], ["ListValue"])
        self._add("Value", ["run"], ["RunStmt"])

        # StrValue
        self._add("StrValue", ["str"], ["str"])

        # BoolValue
        self._add("BoolValue", ["true"], ["true"])
        self._add("BoolValue", ["false"], ["false"])

        # ListValue
        self._add("ListValue", ["["], ["[", "ValueList", "]"])

        # ValueList
        self._add("ValueList", value_first, ["Value", "ValueList'"])
        self._add("ValueList", ["]"], ["ε"])

        # ValueList'
        self._add("ValueList'", [","], [",", "Value", "ValueList'"])
        self._add("ValueList'", ["]"], ["ε"])

    def _token_type(self, token):
        if hasattr(token, "type"):
            return token.type
        return token[0]

    def _token_value(self, token):
        if hasattr(token, "value"):
            return token.value
        return token[1] if len(token) > 1 else token[0]

    def _token_line(self, token):
        return getattr(token, "line", "?")

    def _token_column(self, token):
        return getattr(token, "column", "?")

    # antonio: main LL(1) parsing algorithm as seen in class
    def parse(self, tokens, trace=False):
        stack = ["$", self.start_symbol]
        index = 0
        derivation = []

        while stack:
            top = stack.pop()
            current = tokens[index]
            lookahead = self._token_type(current)

            if trace:
                print(f"STACK: {stack + [top]}")
                print(f"LOOKAHEAD: {lookahead!r}, VALUE: {self._token_value(current)!r}")
                print()

            if top == "ε":
                continue

            # Terminal / EOF
            if top not in self.nonterminals:
                if top == lookahead:
                    index += 1
                else:
                    raise SyntaxError(
                        f"Syntax error at line {self._token_line(current)}, "
                        f"column {self._token_column(current)}: "
                        f"expected {top!r}, found {lookahead!r} "
                        f"({self._token_value(current)!r})"
                    )
                continue

            # Non-terminal
            production = self.table[top].get(lookahead)
            if production is None:
                expected = ", ".join(sorted(self.table[top].keys()))
                raise SyntaxError(
                    f"Syntax error at line {self._token_line(current)}, "
                    f"column {self._token_column(current)}: "
                    f"no rule for non-terminal {top!r} with lookahead {lookahead!r}. "
                    f"Expected one of: {expected}"
                )

            derivation.append(f"{top} -> {' '.join(production)}")

            if production != ["ε"]:
                for symbol in reversed(production):
                    stack.append(symbol)

        if index != len(tokens):
            current = tokens[index]
            raise SyntaxError(
                f"Syntax error at line {self._token_line(current)}, "
                f"column {self._token_column(current)}: "
                f"unconsumed token {self._token_type(current)!r} "
                f"({self._token_value(current)!r})"
            )

        return derivation
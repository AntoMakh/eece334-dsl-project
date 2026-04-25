TYPE_STARTERS = {"string", "int", "bool", "list"}
COMPARISON_OPERATORS = {"==", "!=", ">=", "<=", ">", "<"}


class Scope:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.entries = {}

    def lookup_local(self, name):
        return self.entries.get(name)

    def lookup(self, name):
        scope = self
        while scope is not None:
            entry = scope.lookup_local(name)
            if entry is not None:
                return entry
            scope = scope.parent
        return None

    def declare(self, name, entry):
        if name in self.entries:
            return False
        self.entries[name] = entry
        return True


class SemanticAnalyzer:
    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0
        self.errors = []
        self.agents = {}
        self.system_scope = None
        self.all_scopes = []

    def current(self):
        return self.tokens[self.index]

    def check(self, token_type):
        return self.current().type == token_type

    def accept(self, token_type):
        if self.check(token_type):
            token = self.current()
            self.index += 1
            return token
        return None

    def expect(self, token_type):
        token = self.current()
        if token.type != token_type:
            raise SyntaxError(
                f"Syntax error at line {token.line}, column {token.column}: "
                f"expected {token_type!r}, found {token.type!r} ({token.value!r})"
            )
        self.index += 1
        return token

    def semantic_error(self, token, message):
        self.errors.append(f"line {token.line}, column {token.column}: {message}")

    def make_position(self, line, column):
        class Position:
            pass
        p = Position()
        p.line = line
        p.column = column
        return p

    def analyze(self):
        self.parse_program()
        self.expect("$")
        return {
            "agents": self.agents,
            "system_scope": self.system_scope,
            "scopes": self.all_scopes,
            "errors": self.errors,
            "ok": len(self.errors) == 0,
        }

    def parse_program(self):
        while self.check("agent"):
            self.parse_agent()

        self.expect("system")
        self.expect("{")
        self.system_scope = self.new_scope("system", None)
        self.parse_system_stmt_list(self.system_scope)
        self.expect("}")

    def parse_agent(self):
        self.expect("agent")
        name_token = self.expect("id")

        if name_token.value in self.agents:
            self.semantic_error(name_token, f"agent {name_token.value!r} is already declared")
            agent = self.make_agent_entry(name_token)
        else:
            agent = self.make_agent_entry(name_token)
            self.agents[name_token.value] = agent

        self.expect("{")
        while not self.check("}"):
            if self.check("tool"):
                self.parse_tool(agent)
            elif self.check("task"):
                self.parse_task(agent)
            else:
                token = self.current()
                raise SyntaxError(
                    f"Syntax error at line {token.line}, column {token.column}: "
                    f"expected 'tool', 'task', or '}}', found {token.type!r} ({token.value!r})"
                )
        self.expect("}")

        for task in agent["tasks"].values():
            for action in task["actions"]:
                if action["tool_name"] not in agent["tools"]:
                    self.semantic_error(
                        self.make_position(action["line"], action["column"]),
                        f"tool {action['tool_name']!r} used in task {task['name']!r} "
                        f"of agent {agent['name']!r} was not declared in that agent",
                    )

    def parse_tool(self, agent):
        self.expect("tool")
        tool_token = self.expect("id")

        if tool_token.value in agent["tools"]:
            self.semantic_error(
                tool_token,
                f"tool {tool_token.value!r} is already declared in agent {agent['name']!r}",
            )
            return

        agent["tools"][tool_token.value] = {
            "name": tool_token.value,
            "line": tool_token.line,
            "column": tool_token.column,
        }

    def parse_task(self, agent):
        self.expect("task")
        task_token = self.expect("id")

        duplicate_task = task_token.value in agent["tasks"]
        if duplicate_task:
            self.semantic_error(
                task_token,
                f"task {task_token.value!r} is already declared in agent {agent['name']!r}",
            )

        self.expect("(")
        params = self.parse_param_list()
        self.expect(")")

        return_type = self.make_type("void")
        return_name = None
        return_line = task_token.line
        return_column = task_token.column

        if self.accept("->") is not None:
            return_type = self.parse_type()
            return_token = self.expect("id")
            return_name = return_token.value
            return_line = return_token.line
            return_column = return_token.column

        task = {
            "name": task_token.value,
            "params": params,
            "return_type": self.copy_type(return_type),
            "return_name": return_name,
            "line": task_token.line,
            "column": task_token.column,
            "actions": [],
        }

        if not duplicate_task:
            agent["tasks"][task_token.value] = task

        task_scope = self.new_scope(f"task {agent['name']}.{task['name']}", None)

        for param in params:
            entry = self.make_symbol_entry(
                param["name"], self.copy_type(param["type"]), "parameter",
                param["line"], param["column"]
            )
            if not task_scope.declare(param["name"], entry):
                self.semantic_error(
                    self.make_position(param["line"], param["column"]),
                    f"parameter {param['name']!r} is already declared in task {task['name']!r}",
                )

        if return_name is not None:
            entry = self.make_symbol_entry(
                return_name, self.copy_type(return_type), "return-variable",
                return_line, return_column
            )
            if not task_scope.declare(return_name, entry):
                self.semantic_error(
                    self.make_position(return_line, return_column),
                    f"return variable {return_name!r} conflicts with another name in task {task['name']!r}",
                )

        self.expect("{")
        while not self.check("}"):
            self.parse_action(task_scope, task)
        self.expect("}")

    def parse_param_list(self):
        params = []
        if self.check(")"):
            return params

        while True:
            param_type = self.parse_type()
            name_token = self.expect("id")
            params.append({
                "name": name_token.value,
                "type": self.copy_type(param_type),
                "line": name_token.line,
                "column": name_token.column,
            })

            if self.accept(",") is None:
                break

        return params

    def parse_action(self, scope, task):
        self.expect("action")
        self.expect(":")
        tool_token = self.expect("id")
        task["actions"].append({
            "tool_name": tool_token.value,
            "line": tool_token.line,
            "column": tool_token.column,
        })
        self.expect("(")
        self.parse_argument_list(scope)
        self.expect(")")

    def parse_system_stmt_list(self, scope):
        while not self.check("}"):
            self.parse_system_stmt(scope)

    def parse_system_stmt(self, scope):
        token_type = self.current().type

        if token_type in TYPE_STARTERS:
            self.parse_var_stmt(scope)
        elif token_type == "id":
            self.parse_assignment_stmt(scope)
        elif token_type == "if":
            self.parse_if_stmt(scope)
        elif token_type == "for":
            self.parse_for_stmt(scope)
        elif token_type == "run":
            self.parse_run_stmt(scope)
        else:
            token = self.current()
            raise SyntaxError(
                f"Syntax error at line {token.line}, column {token.column}: "
                f"expected system statement, found {token.type!r} ({token.value!r})"
            )

    def parse_var_stmt(self, scope):
        declared_type = self.parse_type()
        name_token = self.expect("id")
        self.expect("=")

        value_type = self.parse_value(scope)
        self.check_assignment_compatibility(name_token, declared_type, value_type)

        final_type = self.merge_declared_and_value_type(declared_type, value_type)
        entry = self.make_symbol_entry(
            name_token.value, final_type, "variable",
            name_token.line, name_token.column
        )

        if not scope.declare(name_token.value, entry):
            self.semantic_error(
                name_token,
                f"variable {name_token.value!r} is already declared in this scope",
            )

    def parse_assignment_stmt(self, scope):
        name_token = self.expect("id")
        entry = scope.lookup(name_token.value)

        if entry is None:
            self.semantic_error(name_token, f"variable {name_token.value!r} was not declared before use")
            lhs_type = self.make_type("error")
        elif entry["kind"] not in {"variable", "parameter", "return-variable", "loop-variable"}:
            self.semantic_error(name_token, f"name {name_token.value!r} is not assignable")
            lhs_type = self.make_type("error")
        else:
            lhs_type = entry["type"]

        self.expect("=")
        rhs_type = self.parse_value(scope)
        self.check_assignment_compatibility(name_token, lhs_type, rhs_type)

        if entry is not None and lhs_type["name"] == "list" and rhs_type["name"] == "list":
            if lhs_type.get("element") is None and rhs_type.get("element") is not None:
                entry["type"]["element"] = self.copy_type(rhs_type["element"])

    def parse_if_stmt(self, scope):
        if_token = self.expect("if")
        condition_type = self.parse_condition(scope)

        if not self.is_error_or_unknown(condition_type) and condition_type["name"] != "bool":
            self.semantic_error(
                if_token,
                f"if condition must have type bool, got {self.display_type(condition_type)}",
            )

        self.expect("{")
        if_scope = self.new_scope("if-block", scope)
        self.parse_system_stmt_list(if_scope)
        self.expect("}")

    def parse_for_stmt(self, scope):
        self.expect("for")
        iterator_token = self.expect("id")
        self.expect("in")
        iterable_token = self.expect("id")

        iterable_entry = scope.lookup(iterable_token.value)
        iterator_type = self.make_type("unknown")

        if iterable_entry is None:
            self.semantic_error(iterable_token, f"list variable {iterable_token.value!r} was not declared before use")
        elif iterable_entry["type"]["name"] != "list":
            self.semantic_error(
                iterable_token,
                f"for loop must iterate over a list, got {self.display_type(iterable_entry['type'])}",
            )
        elif iterable_entry["type"].get("element") is not None:
            iterator_type = self.copy_type(iterable_entry["type"]["element"])

        self.expect("{")
        for_scope = self.new_scope("for-block", scope)
        iterator_entry = self.make_symbol_entry(
            iterator_token.value, iterator_type, "loop-variable",
            iterator_token.line, iterator_token.column
        )
        for_scope.declare(iterator_token.value, iterator_entry)

        self.parse_system_stmt_list(for_scope)
        self.expect("}")

    def parse_condition(self, scope):
        result_type = self.parse_and_condition(scope)

        while self.accept("or") is not None:
            right_type = self.parse_and_condition(scope)
            self.check_boolean_operand(result_type, "or")
            self.check_boolean_operand(right_type, "or")
            result_type = self.make_type("bool")

        return result_type

    def parse_and_condition(self, scope):
        result_type = self.parse_relational_condition(scope)

        while self.accept("and") is not None:
            right_type = self.parse_relational_condition(scope)
            self.check_boolean_operand(result_type, "and")
            self.check_boolean_operand(right_type, "and")
            result_type = self.make_type("bool")

        return result_type

    def parse_relational_condition(self, scope):
        left_type = self.parse_value(scope)

        op_token = self.current()
        if op_token.type not in COMPARISON_OPERATORS:
            raise SyntaxError(
                f"Syntax error at line {op_token.line}, column {op_token.column}: "
                f"expected comparison operator, found {op_token.type!r} ({op_token.value!r})"
            )

        self.index += 1
        right_type = self.parse_value(scope)

        self.check_comparison(op_token, left_type, right_type)
        return self.make_type("bool")

    def parse_value(self, scope):
        token_type = self.current().type

        if token_type in {"(", "id", "num"}:
            return self.parse_expr(scope)
        if token_type == "str":
            self.expect("str")
            return self.make_type("string")
        if token_type == "true":
            self.expect("true")
            return self.make_type("bool")
        if token_type == "false":
            self.expect("false")
            return self.make_type("bool")
        if token_type == "[":
            return self.parse_list_value(scope)
        if token_type == "run":
            return self.parse_run_stmt(scope)

        token = self.current()
        raise SyntaxError(
            f"Syntax error at line {token.line}, column {token.column}: "
            f"expected value, found {token.type!r} ({token.value!r})"
        )

    def parse_argument_list(self, scope):
        args = []
        if self.check(")"):
            return args

        while True:
            args.append(self.parse_value(scope))
            if self.accept(",") is None:
                break

        return args

    def parse_list_value(self, scope):
        self.expect("[")
        element_type = None

        if not self.check("]"):
            while True:
                current_type = self.parse_value(scope)

                if not self.is_error_or_unknown(current_type):
                    if element_type is None:
                        element_type = self.copy_type(current_type)
                    elif not self.same_type(element_type, current_type, check_list_element=True):
                        self.semantic_error(
                            self.current(),
                            f"list literal has mixed element types: "
                            f"{self.display_type(element_type)} and {self.display_type(current_type)}",
                        )

                if self.accept(",") is None:
                    break

        self.expect("]")
        return self.make_type("list", element_type)

    def parse_run_stmt(self, scope):
        run_token = self.expect("run")
        agent_token = self.expect("id")
        self.expect(".")
        task_token = self.expect("id")
        self.expect("(")
        arg_types = self.parse_argument_list(scope)
        self.expect(")")

        agent = self.agents.get(agent_token.value)
        if agent is None:
            self.semantic_error(agent_token, f"agent {agent_token.value!r} is not declared")
            return self.make_type("error")

        task = agent["tasks"].get(task_token.value)
        if task is None:
            self.semantic_error(
                task_token,
                f"task {task_token.value!r} is not declared in agent {agent['name']!r}",
            )
            return self.make_type("error")

        expected_params = task["params"]

        if len(arg_types) != len(expected_params):
            self.semantic_error(
                run_token,
                f"run {agent['name']}.{task['name']} expects {len(expected_params)} argument(s), "
                f"got {len(arg_types)}",
            )
        else:
            for i in range(len(arg_types)):
                actual = arg_types[i]
                expected = expected_params[i]["type"]

                if self.is_error_or_unknown(actual):
                    continue

                if not self.is_assignable(expected, actual):
                    self.semantic_error(
                        run_token,
                        f"argument {i + 1} of run {agent['name']}.{task['name']} has type "
                        f"{self.display_type(actual)}, expected {self.display_type(expected)}",
                    )

        return self.copy_type(task["return_type"])

    def parse_expr(self, scope):
        left_type = self.parse_term(scope)

        while self.check("+") or self.check("-"):
            op_token = self.current()
            self.index += 1
            right_type = self.parse_term(scope)
            left_type = self.check_arithmetic(op_token, left_type, right_type)

        return left_type

    def parse_term(self, scope):
        left_type = self.parse_factor(scope)

        while self.check("*") or self.check("/"):
            op_token = self.current()
            self.index += 1
            right_type = self.parse_factor(scope)
            left_type = self.check_arithmetic(op_token, left_type, right_type)

        return left_type

    def parse_factor(self, scope):
        if self.accept("(") is not None:
            expr_type = self.parse_expr(scope)
            self.expect(")")
            return expr_type

        if self.check("num"):
            self.expect("num")
            return self.make_type("int")

        if self.check("id"):
            name_token = self.expect("id")
            entry = scope.lookup(name_token.value)

            if entry is None:
                self.semantic_error(name_token, f"variable {name_token.value!r} was not declared before use")
                return self.make_type("error")

            return self.copy_type(entry["type"])

        token = self.current()
        raise SyntaxError(
            f"Syntax error at line {token.line}, column {token.column}: "
            f"expected factor, found {token.type!r} ({token.value!r})"
        )

    def parse_type(self):
        token = self.current()
        if token.type not in TYPE_STARTERS:
            raise SyntaxError(
                f"Syntax error at line {token.line}, column {token.column}: "
                f"expected type, found {token.type!r} ({token.value!r})"
            )

        self.index += 1
        return self.make_type(token.type)

    def make_type(self, name, element=None):
        return {
            "name": name,
            "element": self.copy_type(element) if element is not None else None,
        }

    def copy_type(self, type_info):
        if type_info is None:
            return None

        return {
            "name": type_info["name"],
            "element": self.copy_type(type_info.get("element")),
        }

    def display_type(self, type_info):
        if type_info is None:
            return "None"

        if type_info["name"] == "list" and type_info.get("element") is not None:
            return f"list<{self.display_type(type_info['element'])}>"

        return type_info["name"]

    def is_error_or_unknown(self, type_info):
        return type_info["name"] in {"error", "unknown"}

    def same_type(self, left, right, check_list_element=False):
        if self.is_error_or_unknown(left) or self.is_error_or_unknown(right):
            return True

        if left["name"] != right["name"]:
            return False

        if left["name"] == "list" and check_list_element:
            left_element = left.get("element")
            right_element = right.get("element")

            if left_element is None or right_element is None:
                return True

            return self.same_type(left_element, right_element, check_list_element=True)

        return True

    def is_assignable(self, expected, actual):
        if self.is_error_or_unknown(expected) or self.is_error_or_unknown(actual):
            return True

        if expected["name"] != actual["name"]:
            return False

        if expected["name"] == "list":
            expected_element = expected.get("element")
            actual_element = actual.get("element")

            if expected_element is None or actual_element is None:
                return True

            return self.same_type(expected_element, actual_element, check_list_element=True)

        return True

    def merge_declared_and_value_type(self, declared, value):
        result = self.copy_type(declared)

        if declared["name"] == "list" and value["name"] == "list":
            if value.get("element") is not None:
                result["element"] = self.copy_type(value["element"])

        return result

    def check_assignment_compatibility(self, token, expected, actual):
        if self.is_error_or_unknown(expected) or self.is_error_or_unknown(actual):
            return

        if actual["name"] == "void":
            self.semantic_error(token, "cannot assign the result of a task with no return value")
            return

        if not self.is_assignable(expected, actual):
            self.semantic_error(
                token,
                f"type mismatch: cannot assign {self.display_type(actual)} to {self.display_type(expected)}",
            )

    def check_arithmetic(self, token, left, right):
        if self.is_error_or_unknown(left) or self.is_error_or_unknown(right):
            return self.make_type("error")

        if left["name"] == "int" and right["name"] == "int":
            return self.make_type("int")

        self.semantic_error(
            token,
            f"operator {token.type!r} requires int operands, got "
            f"{self.display_type(left)} and {self.display_type(right)}",
        )
        return self.make_type("error")

    def check_boolean_operand(self, value_type, operator_name):
        if self.is_error_or_unknown(value_type):
            return

        if value_type["name"] != "bool":
            token = self.current()
            self.semantic_error(
                token,
                f"operator {operator_name!r} requires bool operands, got {self.display_type(value_type)}",
            )

    def check_comparison(self, token, left, right):
        if self.is_error_or_unknown(left) or self.is_error_or_unknown(right):
            return

        if token.type in {"==", "!="}:
            if left["name"] == "list" or right["name"] == "list":
                self.semantic_error(token, "list values cannot be compared directly")
                return

            if not self.same_type(left, right):
                self.semantic_error(
                    token,
                    f"comparison {token.type!r} requires matching types, got "
                    f"{self.display_type(left)} and {self.display_type(right)}",
                )
            return

        if left["name"] != "int" or right["name"] != "int":
            self.semantic_error(
                token,
                f"comparison {token.type!r} requires int operands, got "
                f"{self.display_type(left)} and {self.display_type(right)}",
            )

    def new_scope(self, name, parent):
        scope = Scope(name, parent)
        self.all_scopes.append(scope)
        return scope

    def make_symbol_entry(self, name, type_info, kind, line, column):
        return {
            "name": name,
            "type": self.copy_type(type_info),
            "kind": kind,
            "line": line,
            "column": column,
        }

    def make_agent_entry(self, token):
        return {
            "name": token.value,
            "line": token.line,
            "column": token.column,
            "tools": {},
            "tasks": {},
        }


def analyze_tokens(tokens):
    return SemanticAnalyzer(tokens).analyze()


def analyze_code(code):
    from dsl_lexer import tokenize
    return analyze_tokens(tokenize(code))

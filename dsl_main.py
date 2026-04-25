import sys

from dsl_lexer import tokenize
from dsl_ll1_parser import LL1Parser
from dsl_semantic_analyzer import SemanticAnalyzer


DEFAULT_CODE = """
agent Researcher {
    tool web_search
    tool llm
    task gather(string topic) -> string data {
        action: web_search(topic)
        action: llm("summarize results")
    }
}
agent Analyzer {
    tool llm
    task sentiment(string text) -> string result {
        action: llm("detect sentiment")
    }
}
system {
    list topics = ["AI","Robotics","Security"]
    int i = 0
    bool negative_found = false
    for t in topics {
        string data = run Researcher.gather(t)
        string sentiment = run Analyzer.sentiment(data)
        if sentiment == "negative" {
            negative_found = true
        }
        i = i + 1
    }
}
"""

def read_code_from_argument():
    if len(sys.argv) == 1:
        return DEFAULT_CODE
    if len(sys.argv) != 2:
        print("Usage: python dsl_main.py [source_file]")
        sys.exit(1)
    filename = sys.argv[1]
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: file {filename!r} not found.")
        sys.exit(1)


def print_symbol_tables(result):
    print("\nAgents table:")
    for agent_name, agent in result["agents"].items():
        print(f"  agent {agent_name}")
        print(f"    tools: {', '.join(agent['tools'].keys()) if agent['tools'] else '(none)'}")

        if not agent["tasks"]:
            print("    tasks: (none)")

        for task_name, task in agent["tasks"].items():
            params = ", ".join(
                f"{param['name']}: {display_type(param['type'])}"
                for param in task["params"]
            )

            return_type = display_type(task["return_type"])
            if task["return_name"] is not None:
                return_type = f"{return_type} {task['return_name']}"

            print(f"    task {task_name}({params}) -> {return_type}")

    print("\nSystem variables table:")
    for name, entry in result["system_scope"].entries.items():
        print(f"  {name}: {display_type(entry['type'])} ({entry['kind']})")
        
def display_type(type_info):
    if type_info["name"] == "list" and type_info.get("element") is not None:
        return f"list<{display_type(type_info['element'])}>"
    return type_info["name"]

def main():
    code = read_code_from_argument()

    try:
        tokens = tokenize(code)
        parser = LL1Parser()
        parser.parse(tokens, trace=False)
        print("Parsing successful.")
    except SyntaxError as e:
        print("Syntax error:")
        print(e)
        sys.exit(1)

    analyzer = SemanticAnalyzer(tokens)
    result = analyzer.analyze()

    if result["errors"]:
        print("Semantic errors:")
        for error in result["errors"]:
            print(f"  {error}")
        sys.exit(1)

    print("Semantic analysis successful.")
    print_symbol_tables(result)


if __name__ == "__main__":
    main()

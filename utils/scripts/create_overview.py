import argparse
import ast
import os
import subprocess
import sys
import zipfile

exclude_dirs = {
    ".venv",
    "../oldMenus",
    "node_modules",
    "Resources",
    "Utilities",
    "temp",
    ".vscode",
    "cache",
    "exports",
    "logs",
    "metadata",
    "attached_assets",
    "plugins",
    "presets",
    "scripts",
    "systemd",
    "__pycache__",
    ".old",
}
exclude_files = {
    "create_overview.py",
    "package-lock.json",
    "package.json",
    "backend/package-lock.json",
    "backend/package.json",
    "frontend/package-lock.json",
    "frontend/package.json",
    "openai.key",
}


# --- Git Metadata Helper ---
def get_git_metadata(file_path):
    """Return a string with the last commit hash and date if the file is in a git repo."""
    cur_path = os.path.abspath(file_path)
    while cur_path and cur_path != os.path.dirname(cur_path):
        if os.path.isdir(os.path.join(cur_path, ".git")):
            try:
                result = subprocess.check_output(
                    ["git", "log", "-n", "1", "--pretty=format:%h %ad", file_path],
                    stderr=subprocess.DEVNULL,
                    universal_newlines=True,
                )
                return result.strip()
            except Exception:
                return "Git metadata not available"
        cur_path = os.path.dirname(cur_path)
    return "Not in a Git repository"


# --- AST Analysis Functions ---
def extract_docstring(node):
    """Extract the first line of a docstring if available."""
    doc = ast.get_docstring(node)
    if doc:
        return doc.strip().split("\n")[0]
    return ""


def analyze_python_file(file_path, error_logs):
    """
    Analyzes a Python file and returns contextual information including:
      - module_docstring: first-line summary
      - functions_defined: list of dicts with function name,
      - docstring snippet, annotations, line count
      - functions_called: list of function names that are called
      - imports: list of imported modules (dependencies)
      - classes: list of dicts with class name, bases,
      - docstring snippet, and methods (name, docstring, annotations, line count)
      - git_metadata: Git info if available
    Any errors encountered are appended to error_logs.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
        tree = ast.parse(content, file_path)
    except Exception as e:
        msg = f"Error parsing {file_path}: {e}"
        print(msg)
        error_logs.append(msg)
        return {}

    module_docstring = extract_docstring(tree)
    functions_defined = []
    functions_called = []
    imports = []
    classes = []

    class Analyzer(ast.NodeVisitor):
        def __init__(self):
            self.current_class = None

        def visit_FunctionDef(self, node):
            func_info = {
                "name": node.name,
                "doc": extract_docstring(node),
                "args": {},
                "returns": None,
                "lines": (
                    node.end_lineno - node.lineno + 1 if hasattr(node, "end_lineno") else "N/A"
                ),
            }
            for arg in node.args.args:
                if arg.annotation:
                    try:
                        annotation = ast.unparse(arg.annotation)
                    except Exception:
                        annotation = ""
                else:
                    annotation = ""
                func_info["args"][arg.arg] = annotation
            if node.returns:
                try:
                    func_info["returns"] = ast.unparse(node.returns)
                except Exception:
                    func_info["returns"] = ""
            if self.current_class is not None:
                self.current_class["methods"].append(func_info)
            else:
                functions_defined.append(func_info)
            self.generic_visit(node)

        def visit_Call(self, node):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                parts = []
                current = node.func
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                name = ".".join(reversed(parts))
            if name:
                functions_called.append(name)
            self.generic_visit(node)

        def visit_Import(self, node):
            for alias in node.names:
                imports.append(alias.name)
            self.generic_visit(node)

        def visit_ImportFrom(self, node):
            module = node.module if node.module else ""
            for alias in node.names:
                imp = f"{module}.{alias.name}" if module else alias.name
                imports.append(imp)
            self.generic_visit(node)

        def visit_ClassDef(self, node):
            class_info = {
                "name": node.name,
                "bases": [ast.unparse(b) if hasattr(ast, "unparse") else "" for b in node.bases],
                "doc": extract_docstring(node),
                "methods": [],
            }
            prev_class = self.current_class
            self.current_class = class_info
            self.generic_visit(node)
            self.current_class = prev_class
            classes.append(class_info)

    Analyzer().visit(tree)

    analysis = {
        "module_docstring": module_docstring,
        "functions_defined": functions_defined,
        "functions_called": sorted(set(functions_called)),
        "imports": sorted(set(imports)),
        "classes": classes,
        "git_metadata": get_git_metadata(file_path),
    }
    return analysis


def perform_cross_file_analysis(python_files, file_analysis, error_logs):
    """
    Performs cross-file analysis over the provided Python files.
    file_analysis is a dictionary mapping file_path to its analysis.
    Returns a mapping: file_path -> { function_name: [list of files that call that function] }.
    """
    # Build mapping from function names to list of files where they are defined.
    function_definitions = {}
    for file, analysis in file_analysis.items():
        for func in analysis.get("functions_defined", []):
            function_definitions.setdefault(func["name"], []).append(file)
        for cls in analysis.get("classes", []):
            for method in cls.get("methods", []):
                function_definitions.setdefault(method["name"], []).append(file)

    incoming_calls = {file: {} for file in file_analysis}
    for file, analysis in file_analysis.items():
        for called_func in analysis.get("functions_called", []):
            if called_func in function_definitions:
                for def_file in function_definitions[called_func]:
                    if def_file != file:
                        incoming_calls[def_file].setdefault(called_func, []).append(file)
    return incoming_calls


# --- File/Directory Operations ---
def combine_files_in_directory(directory, output_file):
    """
    Combine all files in the directory recursively (with enriched contextual analysis) into one output file.
    Excludes specified directories and files.
    Errors encountered during file processing are collected and reported.
    """
    error_logs = []

    python_files = []
    all_files = []  # List of tuples: (full_file_path, relative_path)
    for root, dirs, files in os.walk(directory):
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith("__") and not d.startswith(".") and d not in exclude_dirs
        ]
        for file in files:
            if file.startswith(".") or file in exclude_files or file.endswith(".txt"):
                continue
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, directory)
            all_files.append((file_path, relative_path))
            if file.endswith(".py"):
                python_files.append(file_path)

    # Cache analysis for each Python file once.
    file_analysis = {}
    for file in python_files:
        file_analysis[file] = analyze_python_file(file, error_logs)

    # Perform cross-file analysis using the cached analysis.
    incoming_calls = perform_cross_file_analysis(python_files, file_analysis, error_logs)

    with open(output_file, "w", encoding="utf-8") as outfile:
        for file_path, relative_path in all_files:
            outfile.write(f"\n\n--- File: {relative_path} ---\n")
            if file_path.endswith(".py"):
                analysis = file_analysis.get(file_path, {})
                outfile.write("### Contextual Analysis ###\n")
                outfile.write(f"Module Docstring: {analysis.get('module_docstring', 'None')}\n")
                outfile.write(f"Git Metadata: {analysis.get('git_metadata', 'N/A')}\n\n")
                outfile.write("Functions Defined:\n")
                for func in analysis.get("functions_defined", []):
                    outfile.write(f"  {func['name']} (Lines: {func['lines']}): {func['doc']}\n")
                    if func["args"]:
                        args = ", ".join(f"{k}: {v}" if v else k for k, v in func["args"].items())
                        outfile.write(f"    Args: {args}\n")
                    if func["returns"]:
                        outfile.write(f"    Returns: {func['returns']}\n")
                outfile.write("\nFunctions Called:\n")
                outfile.write(", ".join(analysis.get("functions_called", [])) + "\n\n")
                outfile.write("Imports / Dependencies:\n")
                outfile.write(", ".join(analysis.get("imports", [])) + "\n\n")
                outfile.write("Classes:\n")
                for cls in analysis.get("classes", []):
                    outfile.write(
                        f"  Class {cls['name']} (Bases: {', '.join(cls['bases'])}) - {cls['doc']}\n"
                    )
                    for method in cls.get("methods", []):
                        outfile.write(
                            f"    Method {method['name']} (Lines: {method['lines']}): {method['doc']}\n"
                        )
                        if method["args"]:
                            args = ", ".join(
                                f"{k}: {v}" if v else k for k, v in method["args"].items()
                            )
                            outfile.write(f"      Args: {args}\n")
                        if method["returns"]:
                            outfile.write(f"      Returns: {method['returns']}\n")
                file_incoming = incoming_calls.get(file_path, {})
                if file_incoming:
                    outfile.write("\nIncoming Calls (from other files):\n")
                    for func, callers in file_incoming.items():
                        outfile.write(f"  {func}: called from {', '.join(callers)}\n")
                else:
                    outfile.write("\nNo incoming calls from other files detected.\n")
            try:
                with open(file_path, "r", encoding="utf-8") as infile:
                    outfile.write("\n--- File Content Start ---\n")
                    outfile.write(infile.read())
                    outfile.write("\n--- File Content End ---\n")
            except Exception as e:
                msg = f"Could not read {file_path}: {e}"
                print(msg)
                error_logs.append(msg)
        # Report errors, if any.
        if error_logs:
            outfile.write("\n### Errors Encountered ###\n")
            for error in error_logs:
                outfile.write(error + "\n")


def combine_files_from_list(file_list, output_file):
    """
    Combine specified files (with enriched contextual
    analysis for Python files) into a single output file.
    Errors encountered during processing are collected and reported.
    """
    error_logs = []
    python_files = [file for file in file_list if file.endswith(".py")]
    file_analysis = {}
    for file in python_files:
        file_analysis[file] = analyze_python_file(file, error_logs)

    incoming_calls = (
        perform_cross_file_analysis(python_files, file_analysis, error_logs) if python_files else {}
    )

    with open(output_file, "w", encoding="utf-8") as outfile:
        for file_path in file_list:
            if not os.path.exists(file_path):
                msg = f"File not found: {file_path}"
                print(msg)
                error_logs.append(msg)
                continue

            outfile.write(f"\n\n--- File: {os.path.abspath(file_path)} ---\n")
            if file_path.endswith(".py"):
                analysis = file_analysis.get(file_path, {})
                outfile.write("### Contextual Analysis ###\n")
                outfile.write(
                    f"Module Docstring: {
                    analysis.get('module_docstring', 'None')}\n"
                )
                outfile.write(
                    f"Git Metadata: {
                    analysis.get('git_metadata', 'N/A')}\n\n"
                )
                outfile.write("Functions Defined:\n")
                for func in analysis.get("functions_defined", []):
                    outfile.write(f"  {func['name']} (Lines: {func['lines']}): {func['doc']}\n")
                    if func["args"]:
                        args = ", ".join(f"{k}: {v}" if v else k for k, v in func["args"].items())
                        outfile.write(f"    Args: {args}\n")
                    if func["returns"]:
                        outfile.write(f"    Returns: {func['returns']}\n")
                outfile.write("\nFunctions Called:\n")
                outfile.write(", ".join(analysis.get("functions_called", [])) + "\n\n")
                outfile.write("Imports / Dependencies:\n")
                outfile.write(", ".join(analysis.get("imports", [])) + "\n\n")
                outfile.write("Classes:\n")
                for cls in analysis.get("classes", []):
                    outfile.write(
                        f"  Class {cls['name']} (Bases: {', '.join(cls['bases'])}) - {cls['doc']}\n"
                    )
                    for method in cls.get("methods", []):
                        outfile.write(
                            f"    Method {method['name']} (Lines: {method['lines']}): {method['doc']}\n"
                        )
                        if method["args"]:
                            args = ", ".join(
                                f"{k}: {v}" if v else k for k, v in method["args"].items()
                            )
                            outfile.write(f"      Args: {args}\n")
                        if method["returns"]:
                            outfile.write(f"      Returns: {method['returns']}\n")
                file_incoming = incoming_calls.get(file_path, {})
                if file_incoming:
                    outfile.write("\nIncoming Calls (from other files):\n")
                    for func, callers in file_incoming.items():
                        outfile.write(f"  {func}: called from {', '.join(callers)}\n")
                    outfile.write("\n")
                else:
                    outfile.write("\nNo incoming calls from other files detected.\n\n")
            try:
                with open(file_path, "r", encoding="utf-8") as infile:
                    outfile.write("\n--- File Content Start ---\n")
                    outfile.write(infile.read())
                    outfile.write("\n--- File Content End ---\n")
            except Exception as e:
                msg = f"Could not read {file_path}: {e}"
                print(msg)
                error_logs.append(msg)
        if error_logs:
            outfile.write("\n### Errors Encountered ###\n")
            for error in error_logs:
                outfile.write(error + "\n")


def zip_files_in_directory_with_context(directory, output_zip):
    """
    Zips all files in the directory recursively (applying the same filters) and
    includes a contextual overview file (with errors) in the archive.
    """
    overview_file = "Project_Overview.txt"
    combine_files_in_directory(directory, overview_file)

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(overview_file, os.path.basename(overview_file))
        for root, dirs, files in os.walk(directory):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith("__") and not d.startswith(".") and d not in exclude_dirs
            ]
            for file in files:
                if (
                    file.startswith(".")
                    or file in exclude_files
                    or file.endswith(".txt")
                    or file.endswith(".zip")
                    or file.endswith(".svg")
                    or file.endswith(".png")
                ):
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, directory)
                zipf.write(file_path, arcname)
    try:
        os.remove(overview_file)
    except Exception as e:
        print(f"Could not remove temporary overview file: {e}")


# --- Main Program and Argument Parsing ---
def main():
    parser = argparse.ArgumentParser(
        description="Combine files with enriched contextual analysis (including errors) or zip directory files recursively along with contextual info."
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Zip all files in the directory recursively (excludes specific files/directories) and include a contextual overview file with errors.",
    )
    parser.add_argument(
        "paths", nargs="*", help="Files to combine or a single directory to process."
    )
    args = parser.parse_args()

    if args.zip:
        if args.paths:
            directory = args.paths[0]
            if not os.path.isdir(directory):
                print(f"Error: {directory} is not a valid directory.")
                sys.exit(1)
        else:
            directory = input("Enter the directory to zip: ").strip()
            if not os.path.isdir(directory):
                print(f"Error: {directory} is not a valid directory.")
                sys.exit(1)
        output_zip = "Project_Files.zip"
        zip_files_in_directory_with_context(directory, output_zip)
        print(f"All files have been zipped into {output_zip}.")
    else:
        output_file = "Project_Overview.txt"
        if args.paths:
            if len(args.paths) == 1 and os.path.isdir(args.paths[0]):
                directory = args.paths[0]
                combine_files_in_directory(directory, output_file)
            else:
                combine_files_from_list(args.paths, output_file)
        else:
            directory = input("Enter the directory to combine files from: ").strip()
            if not os.path.isdir(directory):
                print(f"Error: {directory} is not a valid directory.")
                sys.exit(1)
            combine_files_in_directory(directory, output_file)
        print(f"All files have been combined into {output_file}.")


if __name__ == "__main__":
    main()
import os
import sys
import subprocess

def run_validator(instance_name, solution_path):
    src_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(src_dir, ".."))
    validator_path = os.path.join(project_root, "validator", "Validate.py")
    instance_path = os.path.join(project_root, "data", f"{instance_name}.txt")
    command = [sys.executable, validator_path, "-i", instance_path, "-s", solution_path]
    
    try:
        custom_env = os.environ.copy()
        custom_env["PYTHONPATH"] = project_root + os.pathsep + src_dir + os.pathsep + custom_env.get("PYTHONPATH", "")
        result = subprocess.run(command, text=True, capture_output=True, cwd=project_root, env=custom_env)
        print(result.stdout)
        if result.stderr:
            print("ERRORS:", result.stderr)
        if (
            "is a valid CVRPTWUI solution" in result.stdout
            and "The given solution information is correct" in result.stdout
        ):
            return True
        return False
        
    except Exception as e:
        print(f"An error occurred while trying to run the validator: {e}")
        return False

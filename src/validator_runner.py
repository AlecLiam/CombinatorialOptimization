import os
import sys
import subprocess

def run_validator(instance_name):
    """Runs the unmodified Validate.py script in a background terminal."""
    print("\n" + "="*80)
    print(f"{'RUNNING OFFICIAL VALIDATOR':^80}")
    print("="*80)
    
    src_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(src_dir, ".."))
    validator_path = os.path.join(project_root, "validator", "Validate.py")
    instance_path = os.path.join(project_root, "data", f"{instance_name}.txt")
    solution_path = os.path.join(project_root, "solutions", f"{instance_name}.txt")
    command = [sys.executable, validator_path, "-i", instance_path, "-s", solution_path]
    
    try:
        custom_env = os.environ.copy()
        custom_env["PYTHONPATH"] = project_root + os.pathsep + src_dir + os.pathsep + custom_env.get("PYTHONPATH", "")
        subprocess.run(command, text=True, capture_output=False, cwd=project_root, env=custom_env)
        
    except Exception as e:
        print(f"An error occurred while trying to run the validator: {e}")
        
    print("="*80 + "\n")
import subprocess
from datetime import datetime

def get_git_short_hash():
    """
    Docstring for get_git_short_hash
    """
    try:
        # Run the git command to get the short commit hash of HEAD
        result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], stdout=subprocess.PIPE, check=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error running git command: {e}"
    except FileNotFoundError:
        return "Git executable not found in PATH"


def get_latest_git_tag():
    # Use 'git describe --tags --abbrev=0' to get the latest tag name
    try:
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None # No tags found

def get_git_committer_info():
    # Use 'git show' with a specific format to get name and email
    try:
        # --format='%cn <%ce>' gets committer name and email
        # -s suppresses the diff output
        result = subprocess.check_output(
            ['git', 'show', '-s', '--format=%cn <%ce>', 'HEAD'],
            stderr=subprocess.STDOUT,
            text=True
        ).strip()
        return result
    except subprocess.CalledProcessError as e:
        return f"Error running git command: {e.output}"
    except FileNotFoundError:
        return "Error: 'git' command not found. Is Git installed and in the system PATH?"

def get_commit_date(repo_path='.'):
    # Command to get the last commit date in Unix timestamp format (%ct)
    cmd = ['git', '-C', repo_path, 'log', '-1', '--format=%ct']
    try:
        # Run the command and capture the output
        timestamp_bytes = subprocess.check_output(cmd)
        # Decode the bytes to a string and strip whitespace
        timestamp_str = timestamp_bytes.decode('utf-8').strip()
        # Convert the Unix timestamp to a Python datetime object
        commit_date = datetime.fromtimestamp(int(timestamp_str))
        return commit_date
    except subprocess.CalledProcessError as e:
        print(f"Error running git command: {e}")
        return None
    except ValueError:
        print("Error converting timestamp")
        return None

import os
import git
import zipfile

class ExplorerAgent:
    def __init__(self, repo_code):
        self.file_path = None
        self.repo_path = None
        self.repo_structure = {}
        self.repo_code = repo_code

    def store_file_path(self, file_path):
        """
        Stores a specific file path in the agent.
        """
        if os.path.exists(file_path):
            self.file_path = file_path
        else:
            raise FileNotFoundError(f"The file path {file_path} does not exist.")

    def get_file_code(self):
        """
        Returns a dictionary with the file path as the key and the file's content as the value.
        """
        if not self.file_path:
            raise ValueError("File path is not set. Please set the file path using store_file_path().")
        
        with open(self.file_path, 'r', encoding='utf-8') as file:
            code = file.read()

        return {self.file_path: code}

    def clone_github_repo(self, repo_url, destination_path):
        """
        Clones a GitHub repository to the specified destination path.
        """
        if not os.path.exists(destination_path):
            os.makedirs(destination_path)
        
        git.Repo.clone_from(repo_url, destination_path)
        self.repo_path = destination_path

        # Update the internal structure and code after cloning
        self.repo_structure = self.get_repo_structure()
        self.repo_code = self.read_repo_code()

    def read_repo_code(self):
        """
        Reads all files in the repository and returns a dictionary with file paths as keys and file contents as values.
        """
        if not self.repo_path:
            raise ValueError("Repository path is not set. Please clone or set the repository path.")
        
        code_dict = {}
        for root, _, files in os.walk(self.repo_path):
            for file in files:
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    code_dict[file_path] = f.read()

        self.repo_code = code_dict  # Store the code in the object
        return code_dict

    def get_repo_structure(self):
        """
        Returns the structure of the codebase as a dictionary where keys are directories and values are lists of files.
        """
        if not self.repo_path:
            raise ValueError("Repository path is not set. Please clone or set the repository path.")
        
        structure = {}
        for root, dirs, files in os.walk(self.repo_path):
            relative_root = os.path.relpath(root, self.repo_path)
            structure[relative_root] = files

        self.repo_structure = structure  # Store the structure in the object
        return structure

    def save_file_to_repo(self, file_path, code):
        """
        Saves the provided code to the specified file path within the repository and updates the internal structure and code.
        """
        if not self.repo_path:
            raise ValueError("Repository path is not set. Please clone or set the repository path.")

        full_path = os.path.join(self.repo_path, file_path)

        # Ensure the directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Write the code to the file
        with open(full_path, 'w', encoding='utf-8') as file:
            file.write(code)

        # Update internal code and structure
        self.repo_code[full_path] = code
        relative_path = os.path.relpath(full_path, self.repo_path)
        dir_name = os.path.dirname(relative_path)
        file_name = os.path.basename(relative_path)

        if dir_name in self.repo_structure:
            if file_name not in self.repo_structure[dir_name]:
                self.repo_structure[dir_name].append(file_name)
        else:
            self.repo_structure[dir_name] = [file_name]

    def extract_zip_to_repo(self, zip_file_path, destination_path=None):
        """
        Extracts a zip file to the specified destination path within the repository and updates the internal structure and code.
        """
        if not self.repo_path:
            raise ValueError("Repository path is not set. Please clone or set the repository path.")
        
        destination_path = destination_path or self.repo_path
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(destination_path)

        # Update the internal structure and code after extracting the zip
        self.repo_structure = self.get_repo_structure()
        self.repo_code = self.read_repo_code()
import './style.css'
import { initializeApp } from 'firebase/app'
import { signInWithPopup, GoogleAuthProvider, getAuth, User } from 'firebase/auth';
import ReactDOM from 'react-dom';
import Workspace from './Workspace';
import { FaTrash } from 'react-icons/fa';

const firebaseConfig = {
  apiKey: "", // firebase api key
  authDomain: "", // firebase domain
  databaseURL: "", // firebase db url
  projectId: "",
  storageBucket: "",
  messagingSenderId: "",
  appId: ""
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

let currentUser: User | null = null;
let githubUsername: string | null = null;
let currentWorkspace: string | null = null;

async function getIdToken(): Promise<string | undefined> {
  try {
    if (currentUser) {
      return await currentUser.getIdToken();
    }
    return undefined;
  } catch (error) {
    console.error('Error getting ID token:', error);
    return undefined;
  }
}

async function signInWithGoogle() {
  const provider = new GoogleAuthProvider();
  try {
    // First, try to sign in with a popup
    const result = await signInWithPopup(auth, provider);
    currentUser = result.user;
  } catch (error: any) {
    console.error("Error during popup sign-in:", error);
  }

  // If we reach here, sign-in was successful
  try {
    // Send the ID token to the backend
    const idToken = await currentUser!.getIdToken();
    const response = await fetch('http://localhost:8000/google-signin', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ idToken }),
    });

    if (!response.ok) {
      throw new Error('Failed to sign in with Google on the backend');
    }

    await checkGitHubStatus();
    updateUserStatus();
    updateAuthButtonText();
    toggleGitHubButton();
  } catch (error) {
    console.error("Error during backend sign-in process:", error);
    // Handle the error appropriately (e.g., show an error message to the user)
  }
}

async function setupAuthButton() {
  const authButton = document.getElementById('auth-button');
  if (authButton) {
    authButton.addEventListener('click', async () => {
      if (currentUser) {
        await logout();
      } else {
        await signInWithGoogle();
      }
    });
  }
}

async function checkGitHubStatus() {
  if (currentUser) {
    const idToken = await currentUser.getIdToken();
    try {
      const response = await fetch('http://localhost:8000/github/status', {
        headers: {
          'Authorization': `Bearer ${idToken}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        if (data.linked) {
          githubUsername = data.username;
          updateGitHubStatus();
          toggleGitHubButton();
          setupFetchReposButton();
        }
      }
    } catch (error) {
      console.error('Error checking GitHub status:', error);
    }
  }
}

function updateUserStatus() {
  const userStatusElement = document.getElementById('user-status');
  if (userStatusElement) {
    userStatusElement.textContent = currentUser ? `${currentUser.displayName}` : '';
  }
}

function updateGitHubStatus() {
  const githubStatusElement = document.getElementById('github-status');
  if (githubStatusElement) {
    githubStatusElement.textContent = githubUsername ? `GitHub account linked: ${githubUsername}` : '';
  }
}

async function logout() {
  try {
    const idToken = await currentUser?.getIdToken();
    await fetch('http://localhost:8000/logout', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${idToken}`
      }
    });
    await auth.signOut();
    currentUser = null;
    githubUsername = null;
    updateGitHubStatus();
    updateUserStatus();
    updateAuthButtonText();
    toggleGitHubButton();
    
    // Clear URL parameters and redirect to home page
    window.history.replaceState({}, document.title, "/");
  } catch (error) {
    console.error("Error during logout:", error);
  }
}

function updateAuthButtonText() {
  const authButton = document.getElementById('auth-button');
  if (authButton) {
    authButton.textContent = currentUser ? 'Sign Out' : 'Sign In';
  }
}

function setupGitHubButton() {
  const githubButton = document.getElementById('github-button');
  if (githubButton) {
    githubButton.addEventListener('click', () => {
      if (currentUser) {
        initiateGitHubOAuth();
      }
    });
  }
}

function toggleGitHubButton() {
  const githubButton = document.getElementById('github-button');
  if (githubButton) {
    githubButton.style.display = currentUser && !githubUsername ? 'block' : 'none';
  }
}

async function initiateGitHubOAuth() {
  const clientId = 'Iv23limcCf9RuRZCUHu9';
  const redirectUri = encodeURIComponent('http://localhost:8000/login/callback');
  const scope = 'repo,user';
  
  const idToken = await currentUser?.getIdToken();
  
  const githubAuthUrl = `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&scope=${scope}&state=${encodeURIComponent(idToken!)}`;
  
  window.location.href = githubAuthUrl;
}

async function fetchGitHubRepos() {
  const reposElement = document.getElementById('github-repos');
  if (!reposElement) return;

  if (!currentUser) {
    reposElement.innerHTML = '<p>Please sign in to view your GitHub repositories.</p>';
    return;
  }

  if (!githubUsername) {
    reposElement.innerHTML = '<p>Please link your GitHub account to view your repositories.</p>';
    return;
  }

  try {
    const idToken = await currentUser.getIdToken();
    const response = await fetch('http://localhost:8000/github/repos', {
      headers: {
        'Authorization': `Bearer ${idToken}`
      }
    });

    if (response.ok) {
      const data = await response.json();
      renderGitHubRepos(data.repos);
    } else if (response.status === 401) {
      reposElement.innerHTML = '<p>Your GitHub session has expired. Please re-link your GitHub account.</p>';
      githubUsername = null;
      updateGitHubStatus();
      toggleGitHubButton();
    } else {
      throw new Error('Failed to fetch GitHub repositories');
    }
  } catch (error) {
    console.error('Error fetching GitHub repositories:', error);
    reposElement.innerHTML = '<p>An error occurred while fetching your repositories. Please try again later.</p>';
  }
}

function renderGitHubRepos(repos: any[]) {
  const reposElement = document.getElementById('github-repos');
  if (!reposElement) return;

  const dropdownContainer = document.createElement('div');
  dropdownContainer.className = 'custom-dropdown';
  
  const dropdownHeaderWrapper = document.createElement('div');
  dropdownHeaderWrapper.className = 'dropdown-header';
  
  const dropdownHeaderText = document.createElement('div');
  dropdownHeaderText.textContent = 'Select a repository';
  dropdownHeaderWrapper.appendChild(dropdownHeaderText);
  
  dropdownContainer.appendChild(dropdownHeaderWrapper);

  // Create search input (hidden by default)
  const searchInput = document.createElement('input');
  searchInput.type = 'text';
  searchInput.placeholder = 'Search repositories...';
  searchInput.className = 'repo-search-input';
  searchInput.style.display = 'none';
  dropdownContainer.appendChild(searchInput);
  
  const dropdownList = document.createElement('ul');
  dropdownList.className = 'dropdown-list';
  dropdownList.style.display = 'none';
  
  function createRepoListItem(repo: any) {
    const listItem = document.createElement('li');
    listItem.innerHTML = `
      <strong>${repo.name}</strong> 
      <span class="repo-visibility">${repo.private ? 'Private' : 'Public'}</span><br>
      <span class="repo-description">${repo.description || 'No description'}</span><br>
      <span class="repo-language">Language: ${repo.language}</span>
    `;
    listItem.addEventListener('click', async () => {
      dropdownHeaderText.textContent = repo.name;
      toggleDropdown(false);
      await addToWorkspace(repo.name);
      await displayPastRepos();
    });
    return listItem;
  }

  function filterRepos(searchTerm: string) {
    const filteredRepos = repos.filter(repo => 
      repo.name.toLowerCase().includes(searchTerm.toLowerCase())
    );
    dropdownList.innerHTML = '';
    filteredRepos.forEach(repo => {
      dropdownList.appendChild(createRepoListItem(repo));
    });
  }

  repos.forEach(repo => {
    dropdownList.appendChild(createRepoListItem(repo));
  });
  
  dropdownContainer.appendChild(dropdownList);
  
  function toggleDropdown(show: boolean) {
    dropdownList.style.display = show ? 'block' : 'none';
    searchInput.style.display = show ? 'block' : 'none';
    if (show) {
      searchInput.focus();
    } else {
      searchInput.value = '';
      filterRepos('');
    }
  }

  // Toggle dropdown on header click
  dropdownHeaderWrapper.addEventListener('click', () => {
    const isCurrentlyHidden = dropdownList.style.display === 'none';
    toggleDropdown(isCurrentlyHidden);
  });

  // Add search functionality
  searchInput.addEventListener('input', (e) => {
    const searchTerm = (e.target as HTMLInputElement).value;
    filterRepos(searchTerm);
  });
  
  // Create the dropdown container
  const repoSectionContainer = document.createElement('div');
  repoSectionContainer.appendChild(dropdownContainer);
  
  // Clear previous content and add the new dropdown
  reposElement.innerHTML = '<h2 class="text-2xl font-bold mb-4">GitHub Repositories</h2>';
  reposElement.appendChild(repoSectionContainer);

  // Close dropdown when clicking outside
  document.addEventListener('click', (event) => {
    if (!dropdownContainer.contains(event.target as Node)) {
      toggleDropdown(false);
    }
  });
}

async function fetchRepoContents(repoName: string): Promise<any> {
  if (!currentUser) {
    console.error("User not authenticated");
    return null;
  }

  try {
    const idToken = await currentUser.getIdToken();
    const response = await fetch(`http://localhost:8000/repos/${repoName}/files/content`, {
      headers: {
        'Authorization': `Bearer ${idToken}`
      }
    });

    if (!response.ok) {
      throw new Error('Failed to fetch repository contents');
    }

    const data = await response.json();
    return data.contents;
  } catch (error) {
    console.error('Error fetching repository contents:', error);
    return null;
  }
}

async function addToWorkspace(repoName: string) {
  if (currentWorkspace === repoName) {
    console.log('Repository is already in the workspace');
    return;
  }

  try {
    const contents = await fetchRepoContents(repoName);
    if (contents) {
      currentWorkspace = repoName;
      displayWorkspace(repoName, contents);
      await displayPastRepos();
    } else {
      throw new Error('Failed to fetch repository contents');
    }
  } catch (error) {
    console.error('Error adding repository to workspace:', error);
  }
}

function setupFetchReposButton() {
  const fetchReposButton = document.getElementById('fetch-repos-button');
  if (fetchReposButton) {
    fetchReposButton.style.display = currentUser && githubUsername ? 'block' : 'none';
    fetchReposButton.addEventListener('click', fetchGitHubRepos);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setupFetchReposButton();
});

async function uploadZipFile(file: File) {
  if (!currentUser) {
    console.error("User not authenticated");
    return { success: false, message: "User not authenticated" };
  }

  const formData = new FormData();
  formData.append('file', file);
  formData.append('repo_type', 'zip');
  formData.append('repo_name', file.name.replace('.zip', ''));

  try {
    const idToken = await currentUser.getIdToken();
    console.log('Sending request to upload zip file');
    const response = await fetch('http://localhost:8000/upload-repo', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${idToken}`
      },
      body: formData
    });

    console.log('Response status:', response.status);
    const result = await response.json();
    console.log('Response data:', result);

    if (!response.ok) {
      console.error('Failed to upload zip file:', result.message);
      return { success: false, message: result.message || 'Failed to upload zip file' };
    }

    if (result.success) {
      console.log('Upload successful:', result);
      await displayPastRepos();
      return { 
        success: true, 
        repoName: result.message.split(': ')[1], // Extract repo name from the message
        contents: result.contents,
        ...result 
      };
    } else {
      console.error('Upload failed:', result.message);
      return { success: false, message: result.message || 'Upload failed' };
    }
  } catch (error) {
    console.error('Error uploading zip file:', error);
    return { success: false, message: 'Error uploading zip file: ' + error.message };
  }
}

// Make openRepo a global function
window.openRepo = async function(repoHash: string, repoName: string) {
  console.log(`Opening repository: ${repoName} (${repoHash})`);
  
  if (!currentUser) {
    console.error("User not authenticated");
    alert("Please sign in to open a repository.");
    return;
  }

  try {
    const idToken = await currentUser.getIdToken();
    const response = await fetch(`http://localhost:8000/repos/${repoName}/files/content`, {
      headers: {
        'Authorization': `Bearer ${idToken}`
      }
    });

    if (!response.ok) {
      throw new Error('Failed to fetch repository contents');
    }

    const data = await response.json();
    
    if (data.contents) {
      currentWorkspace = repoName;
      displayWorkspace(repoName, data.contents);
    } else {
      throw new Error('Repository contents are empty');
    }
  } catch (error) {
    console.error('Error opening repository:', error);
    alert(`Failed to open repository: ${error.message}`);
  }
};

async function deletePastRepo(repoHash: string) {
  if (!currentUser) {
    console.error("User not authenticated");
    alert("Please sign in to delete a repository.");
    return;
  }

  try {
    const idToken = await currentUser.getIdToken();
    const response = await fetch(`http://localhost:8000/delete-repo/${repoHash}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${idToken}`
      }
    });

    if (!response.ok) {
      throw new Error('Failed to delete repository');
    }

    if (response.ok) {
      await displayPastRepos();
      return true;
    }
  } catch (error) {
    console.error('Error deleting repository:', error);
    alert(`Failed to delete repository: ${error.message}`);
    return false;
  }
}

async function displayPastRepos() {
  const pastReposElement = document.getElementById('past-repos');
  if (!pastReposElement) return;

  if (!currentUser) {
    pastReposElement.innerHTML = '<p>Please sign in to view past repositories.</p>';
    return;
  }

  pastReposElement.innerHTML = '<p>Loading past repositories...</p>';

  try {
    const idToken = await currentUser.getIdToken();
    const response = await fetch('http://localhost:8000/past-repo', {
      headers: {
        'Authorization': `Bearer ${idToken}`
      }
    });

    if (!response.ok) {
      throw new Error('Failed to fetch past repositories');
    }

    const data = await response.json();
    const repos = data.repos;

    pastReposElement.innerHTML = ''; // Clear the loading message

    // Create and append the header
    const header = document.createElement('div');
    header.className = 'mb-6';
    header.innerHTML = `
      <h2 class="text-2xl font-bold text-white">Past Repositories</h2>
    `;
    pastReposElement.appendChild(header);

    if (repos.length === 0) {
      pastReposElement.innerHTML += '<p>No past repositories available.</p>';
      return;
    }

    const repoList = document.createElement('ul');
    repoList.className = 'space-y-4';

    repos.forEach((repo) => {
      const li = document.createElement('li');
      li.className = 'bg-gray-800 p-4 rounded-lg relative';
      li.innerHTML = `
        <h3 class="text-lg font-semibold">${repo.name}</h3>
        <p class="text-sm text-gray-400">Type: ${repo.type}</p>
        <p class="text-sm text-gray-400">Uploaded: ${new Date(repo.upload_date).toLocaleString()}</p>
        <button class="open-repo-btn mt-2 bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition duration-300" 
                data-repo-hash="${repo.hash}" data-repo-name="${repo.name}">
          Open in Workspace
        </button>
        <button class="delete-repo-btn absolute top-2 right-2 text-red-500 hover:text-red-700 transition duration-300" 
                data-repo-hash="${repo.hash}" data-repo-name="${repo.name}">
          <FaTrash />
        </button>
      `;
      repoList.appendChild(li);
    });

    pastReposElement.appendChild(repoList);

    // Attach event listeners to the "Open in Workspace" buttons
    const openRepoButtons = pastReposElement.querySelectorAll('.open-repo-btn');
    openRepoButtons.forEach(button => {
      button.addEventListener('click', function() {
        const repoHash = this.getAttribute('data-repo-hash');
        const repoName = this.getAttribute('data-repo-name');
        window.openRepo(repoHash, repoName);
      });
    });

    // Attach event listeners to the delete buttons
    const deleteRepoButtons = pastReposElement.querySelectorAll('.delete-repo-btn');
    deleteRepoButtons.forEach(button => {
      button.addEventListener('click', async function() {
        const repoHash = this.getAttribute('data-repo-hash');
        const repoName = this.getAttribute('data-repo-name');
        
        if (confirm(`Are you sure you want to delete the repository "${repoName}"? This action cannot be undone.`)) {
          const deleted = await deletePastRepo(repoHash);
          if (deleted) {
            await displayPastRepos();
          }
        }
      });
    });
  } catch (error) {
    console.error('Error fetching past repositories:', error);
    pastReposElement.innerHTML = '<p>Error loading past repositories. Please try again later.</p>';
  }
}

// Modify the displayWorkspace function to handle potential errors
function displayWorkspace(repoName: string, contents: any) {
  const workspaceContainer = document.getElementById('workspace-container');
  if (!workspaceContainer) {
    console.error('Workspace container not found');
    return;
  }

  // Clear previous content
  ReactDOM.unmountComponentAtNode(workspaceContainer);
  workspaceContainer.innerHTML = '';

  const workspaceRepo = {
    name: repoName,
    files: contents
  };

  try {
    ReactDOM.render(
      <Workspace
        workspaceRepo={workspaceRepo}
        removeFromWorkspace={() => {
          closeWorkspace();
        }}
        getIdToken={getIdToken}
      />,
      workspaceContainer
    );

    // Show the workspace container
    workspaceContainer.style.display = 'flex';
    document.body.classList.add('workspace-open');
  } catch (error) {
    console.error('Error rendering workspace:', error);
    alert('Failed to render workspace. Please try again.');
    closeWorkspace();
  }
}

// Add this function to close the workspace
function closeWorkspace() {
  const workspaceContainer = document.getElementById('workspace-container');
  if (workspaceContainer) {
    ReactDOM.unmountComponentAtNode(workspaceContainer);
    workspaceContainer.style.display = 'none';
  }
  document.body.classList.remove('workspace-open');
  currentWorkspace = null;
}

function setupUploadSection() {
  const uploadForm = document.getElementById('upload-form');
  const fileInput = document.getElementById('file-input') as HTMLInputElement;
  const fileNameDisplay = document.getElementById('file-name-display');
  const uploadButton = document.getElementById('upload-button');
  const submitButton = document.getElementById('submit-button');
  const uploadStatus = document.getElementById('upload-status');

  if (uploadForm && fileInput && fileNameDisplay && uploadButton && submitButton && uploadStatus) {
    // Trigger file input when the upload button is clicked
    uploadButton.addEventListener('click', () => {
      fileInput.click();
    });

    fileInput.addEventListener('change', (event) => {
      const target = event.target as HTMLInputElement;
      if (target.files && target.files.length > 0) {
        fileNameDisplay.textContent = target.files[0].name;
        submitButton.style.display = 'block';
      } else {
        fileNameDisplay.textContent = '';
        submitButton.style.display = 'none';
      }
    });

    uploadForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (fileInput.files && fileInput.files.length > 0) {
        uploadStatus.textContent = 'Uploading...';
        try {
          const result = await uploadZipFile(fileInput.files[0]);
          console.log('Upload result:', result);
          if (result.success) {
            uploadStatus.textContent = `Upload successful!`;
            fileInput.value = '';
            fileNameDisplay.textContent = '';
            submitButton.style.display = 'none';
            await displayPastRepos();
            
            // Open the uploaded repository in the workspace
            if (result.repoName && result.contents) {
              displayWorkspace(result.repoName, result.contents);
            }
          } else {
            uploadStatus.textContent = `Upload failed: ${result.message}`;
          }
        } catch (error) {
          console.error('Error in form submission:', error);
          uploadStatus.textContent = 'Upload failed. Please try again. Error: ' + error.message;
        }
      }
    });
  }
}

function updateMainContent() {
  const mainContent = document.getElementById('main-content');
  if (!mainContent) return;

  mainContent.innerHTML = `
    <div class="flex flex-col space-y-8">
      <section id="new-repos" class="bg-[#1a1a1a] p-6 rounded-lg shadow-lg">
        <div class="flex flex-col lg:flex-row lg:space-x-8 space-y-8 lg:space-y-0">
          <div id="github-repos" class="lg:w-1/2 p-4 bg-[#242424] rounded-lg">
            <h2 class="text-2xl font-bold mb-4">GitHub Repositories</h2>
            <p>Loading...</p>
          </div>
          <div id="upload-repo" class="lg:w-1/2 p-4 bg-[#242424] rounded-lg">
            <h2 class="text-2xl font-bold mb-4">Add to Workspace</h2>
            <form id="upload-form" class="space-y-1">
              <input type="file" id="file-input" accept=".zip" class="hidden">
              <button type="button" id="upload-button" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition duration-300">
                Select Zip File
              </button>
              <div id="file-name-display" class="text-sm"></div>
              <button type="submit" id="submit-button" class="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded transition duration-300 hidden">
                Add to Workspace
              </button>
            </form>
            <div id="upload-status" class="text-sm mt-2"></div>
          </div>
        </div>
      </section>
      <div class="border-b border-gray-600"></div>
      <section id="past-repos" class="bg-[#1a1a1a] p-6 rounded-lg shadow-lg">
        <h2 class="text-2xl font-bold mb-4">Past Repositories</h2>
        <p>Loading...</p>
      </section>
    </div>
  `;

  setupUploadSection();
  fetchGitHubRepos();
  displayPastRepos();
}

// Update the auth state change handler
auth.onAuthStateChanged(async (user) => {
  if (user) {
    currentUser = user;
    await checkGitHubStatus();
    updateUserStatus();
    updateAuthButtonText();
    toggleGitHubButton();
    updateMainContent();
  } else {
    currentUser = null;
    githubUsername = null;
    updateUserStatus();
    updateGitHubStatus();
    updateAuthButtonText();
    toggleGitHubButton();
    updateMainContent();
  }
});

// Make sure to call updateMainContent on initial load
document.addEventListener('DOMContentLoaded', () => {
  updateMainContent();
});

// Update the handleGitHubLinked function
function handleGitHubLinked() {
  const urlParams = new URLSearchParams(window.location.search);
  const username = urlParams.get('username');
  
  if (username && currentUser) {
    console.log('GitHub account linked successfully:', username);
    githubUsername = username;
    updateGitHubStatus();
    toggleGitHubButton();
    updateMainContent();
    // Clear URL parameters
    window.history.replaceState({}, document.title, "/");
  } else if (username && !currentUser) {
    // Clear URL parameters if there's no current user
    window.history.replaceState({}, document.title, "/");
  }
}

document.querySelector<HTMLDivElement>('#app')!.innerHTML = `
<div id="app-container" class="min-h-screen bg-[#242424] text-[rgba(255,255,255,0.87)]">
  <header id="app-header" class="bg-[#1a1a1a] p-4 flex justify-between items-center shadow-md w-full">
    <h1 class="text-2xl font-bold">Langhub</h1>
    <div id="header-right" class="flex items-center space-x-4">
      <div id="user-status" class="text-sm"></div>
      <div id="github-status" class="text-sm"></div>
      <div id="button-container" class="flex space-x-2">
        <button id="auth-button" class="bg-[#646cff] hover:bg-[#535bf2] text-white font-bold py-2 px-4 rounded transition duration-300">Sign In</button>
        <button id="github-button" class="bg-gray-600 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded transition duration-300" style="display: none;">Link GitHub</button>
      </div>
    </div>
  </header>
  <main id="main-content" class="p-4">
    <div class="content-container flex flex-col space-y-8">
      <section id="new-repos" class="bg-[#1a1a1a] p-6 rounded-lg shadow-lg">
        <div class="flex flex-col lg:flex-row space-y-6 lg:space-y-0 lg:space-x-6">
          <div id="github-repos" class="lg:w-2/3">
            <h2 class="text-2xl font-bold mb-4">GitHub Repositories</h2>
            <!-- Repo selector dropdown will be inserted here -->
          </div>
          <div id="upload-repo" class="lg:w-1/3">
            <h2 class="text-2xl font-bold mb-4">Add to Workspace</h2>
            <form id="upload-form">
              <input type="file" id="file-input" accept=".zip" style="display: none;">
              <button type="button" id="upload-button" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition duration-300">
                Select Zip File
              </button>
              <div id="file-name-display" class="text-sm mt-2"></div>
              <button type="submit" id="submit-button" class="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded transition duration-300 mt-4" style="display: none;">
                Add to Workspace
              </button>
            </form>
            <div id="upload-status" class="text-sm mt-2"></div>
          </div>
        </div>
      </section>
      <div class="border-b border-gray-600"></div>
      <section id="past-repos" class="bg-[#1a1a1a] p-6 rounded-lg shadow-lg">
        <h2 class="text-2xl font-bold mb-4">Past Repositories</h2>
        <!-- Past repos will be inserted here -->
      </section>
    </div>
  </main>
</div>
`;

auth.onAuthStateChanged(async (user) => {
  if (user) {
    currentUser = user;
    await checkGitHubStatus();
    updateUserStatus();
    updateAuthButtonText();
    toggleGitHubButton();
    if (githubUsername) {
      setupFetchReposButton();
    }
  } else {
    currentUser = null;
    githubUsername = null;
    updateUserStatus();
    updateGitHubStatus();
    updateAuthButtonText();
    toggleGitHubButton();
    // Hide the fetch repos button when logged out
    const fetchReposButton = document.getElementById('fetch-repos-button');
    if (fetchReposButton) {
      fetchReposButton.style.display = 'none';
    }
  }
});

// Initial setup
document.body.insertAdjacentHTML('beforeend', '<div id="workspace-container" style="display: none;"></div>');
document.addEventListener('DOMContentLoaded', () => {
  setupAuthButton();
  setupGitHubButton();
  setupUploadSection();
  updateUserStatus();
  updateGitHubStatus();
  updateAuthButtonText();
  toggleGitHubButton();
  displayPastRepos();
  updateMainContent();
});

// Check for GitHub username parameter on initial load
handleGitHubLinked();
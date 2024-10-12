import React, { useState, useCallback, useEffect} from 'react';
import { FaFolder, FaFolderOpen, FaFile, FaInfoCircle, FaProjectDiagram } from 'react-icons/fa';
import { Container, Orientation } from './Resizable';
import Chat from './Chat';
import NodesPanel from './NodesPanel';
import toast from 'react-hot-toast';
import axios from 'axios';
import { Editor } from '@monaco-editor/react';

interface FileStructure {
  [key: string]: string | FileStructure;
}

interface WorkspaceRepo {
  name: string;
  files: FileStructure;
  ignored_files?: string[];
}

interface WorkspaceProps {
  workspaceRepo: {
    name: string;
    files: FileStructure;
    ignored_files?: string[];
  };
  removeFromWorkspace: () => void;
  getIdToken: () => Promise<string | undefined>;
}


const FileTree: React.FC<{
  structure: FileStructure;
  onSelectFile: (path: string, content: string) => void;
  path?: string;
}> = ({ structure, onSelectFile, path = '' }) => {
  const [expanded, setExpanded] = useState<{ [key: string]: boolean }>({});

  const toggleExpand = (key: string) => {
    setExpanded(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const renderFileTree = (struct: FileStructure, currentPath: string) => {
    return Object.entries(struct).map(([key, value]) => {
      if (key === 'ignored_files') return null;
      const newPath = currentPath ? `${currentPath}/${key}` : key;
      if (typeof value === 'string') {
        return (
          <li
            key={newPath}
            className="cursor-pointer text-gray-300 hover:text-gray-100 flex items-center py-1"
            onClick={() => onSelectFile(newPath, value)}
          >
            <FaFile className="mr-2 text-blue-400" />
            {key}
          </li>
        );
      } else {
        return (
          <li key={newPath} className="py-1">
            <div
              className="cursor-pointer text-gray-300 hover:text-gray-100 flex items-center"
              onClick={() => toggleExpand(newPath)}
            >
              {expanded[newPath] ? (
                <FaFolderOpen className="mr-2 text-yellow-400" />
              ) : (
                <FaFolder className="mr-2 text-yellow-400" />
              )}
              {key}
            </div>
            {expanded[newPath] && (
              <ul className="ml-4">
                {renderFileTree(value as FileStructure, newPath)}
              </ul>
            )}
          </li>
        );
      }
    });
  };

  return <ul className="ml-4">{renderFileTree(structure, path)}</ul>;
};

const Workspace: React.FC<WorkspaceProps> = ({ workspaceRepo, removeFromWorkspace, getIdToken }) => {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [selectedFileContent, setSelectedFileContent] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [showIgnoredFiles, setShowIgnoredFiles] = useState(false);
  const [showNodesPanel, setShowNodesPanel] = useState(false);

  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [hasUnsavedChanges]);

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      setSelectedFileContent(value);
      setIsEditing(true);
      setHasUnsavedChanges(true);
    }
  };

  const handleSave = async () => {
    if (!selectedFile || !selectedFileContent) return;
  
    setIsSaving(true);
    try {
      const idToken = await getIdToken();
      if (!idToken) {
        throw new Error('Not authenticated');
      }
      const response = await axios.post('http://localhost:8000/api/save-file', {
        repo: workspaceRepo.name,
        path: selectedFile,
        content: selectedFileContent,
        message: `Update ${selectedFile}`
      }, {
        headers: {
          'Authorization': `Bearer ${idToken}`
        }
      });
      
      toast.success('File saved successfully');
      setIsEditing(false);
      setHasUnsavedChanges(false);
    } catch (error) {
      console.error('Error saving file:', error);
      if (axios.isAxiosError(error)) {
        if (error.response?.status === 401) {
          toast.error('Your session has expired. Please log in again.');
          // Implement a function to redirect to login page or refresh the token
        } else if (error.response?.status === 403) {
          toast.error('You do not have permission to modify this file.');
        } else if (error.response?.status === 404) {
          toast.error('The file or repository was not found.');
        } else {
          toast.error(`Failed to save file: ${error.response?.data?.detail || error.message}`);
        }
      } else {
        toast.error('Failed to save file: Unknown error');
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleFileSelect = useCallback((path: string, content: string) => {
    setSelectedFile(path);
    setSelectedFileContent(content);
    setIsEditing(false);
  }, []);

  const toggleIgnoredFiles = () => {
    setShowIgnoredFiles(!showIgnoredFiles);
  };

  const getLanguage = useCallback((filename: string) => {
    const extension = filename.split('.').pop()?.toLowerCase();
    switch (extension) {
      case 'js':
        return 'javascript';
      case 'ts':
        return 'typescript';
      case 'tsx':
        return 'typescript';
      case 'py':
        return 'python';
      case 'html':
        return 'html';
      case 'css':
        return 'css';
      case 'json':
        return 'json';
      case 'go':
        return 'go';
      case 'sum':
        return 'go';
      case 'mod':
        return 'go';
      case 'cpp':
        return 'cpp';
      case 'ipynb':
        return 'python';
      default:
        return 'plaintext';
    }
  }, []);

  const toggleNodesPanel = () => {
    setShowNodesPanel(!showNodesPanel);
  };

  const FileTreeComponent = (
    <div className="h-full bg-black overflow-y-auto">
      <div className="p-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold text-gray-100">{workspaceRepo.name}</h2>
          <div>
            <button
              onClick={toggleNodesPanel}
              className="px-3 py-1 bg-blue-600 text-white hover:bg-blue-700 transition-colors rounded mr-2"
            >
              <FaProjectDiagram className="mr-1 inline" />
              Nodes
            </button>
            <button
              onClick={removeFromWorkspace}
              className="px-3 py-1 bg-red-700 text-white hover:bg-red-800 transition-colors rounded"
            >
              Remove
            </button>
          </div>
        </div>
        <FileTree
          structure={workspaceRepo.files}
          onSelectFile={handleFileSelect}
        />
        {workspaceRepo.ignored_files && workspaceRepo.ignored_files.length > 0 && (
          <div className="mt-4">
            <div 
              className="text-yellow-400 flex items-center cursor-pointer hover:text-yellow-300"
              onClick={toggleIgnoredFiles}
            >
              <FaInfoCircle className="mr-2" />
              <span>Some files were ignored</span>
              {/* {showIgnoredFiles ? <FaChevronDown className="ml-2" /> : <FaChevronRight className="ml-2" />} */}
            </div>
            {showIgnoredFiles && (
              <ul className="mt-2 ml-6 text-gray-400">
                {workspaceRepo.ignored_files.map((file, index) => (
                  <li key={index} className="py-1">
                    <FaFile className="mr-2 text-gray-500 inline" />
                    {file}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );

  const EditorComponent = (
    <div className="h-full bg-black overflow-hidden flex flex-col">
      {selectedFile && selectedFileContent ? (
        <>
          <div className="flex justify-between items-center bg-gray-900 border-b border-gray-700">
            <h3 className="text-xl font-semibold p-4 text-gray-100">{selectedFile}</h3>
            <button
              onClick={handleSave}
              disabled={!isEditing || isSaving}
              className={`px-4 py-2 mr-4 ${
                isEditing && !isSaving
                  ? 'bg-blue-600 hover:bg-blue-700 text-white'
                  : 'bg-gray-600 text-gray-400 cursor-not-allowed'
              }`}
            >
              {isSaving ? 'Saving...' : 'Save'}
            </button>
          </div>
          <div className="flex-grow">
            <Editor
              key={selectedFile}
              height="100%"
              language={getLanguage(selectedFile)}
              value={selectedFileContent}
              theme="vs-dark"
              onChange={handleEditorChange}
              options={{
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                fontSize: 14,
              }}
            />
          </div>
        </>
      ) : (
        <div className="h-full flex items-center justify-center text-gray-400">
          Select a file to view its content
        </div>
      )}
    </div>
  );

  const WorkspaceContent = (
    <Container
      orientation={Orientation.HORIZONTAL}
      className="h-full overflow-hidden"
      initialSize={300}
      firstChild={FileTreeComponent}
      firstClassName="overflow-hidden"
      secondChild={
        showNodesPanel ? (
          <Container
            orientation={Orientation.VERTICAL}
            className="h-full overflow-hidden"
            initialSize={window.innerHeight / 2}
            firstChild={EditorComponent}
            firstClassName="overflow-hidden"
            secondChild={
              <NodesPanel 
                getIdToken={() => getIdToken()} 
                repoName={workspaceRepo.name} 
              />
            }
            secondClassName="overflow-hidden border-t border-gray-700"
          />
        ) : (
          EditorComponent
        )
      }
      secondClassName="overflow-hidden"
    />
  );

  return (
    <div className="h-full p-4">
      <Container
        orientation={Orientation.HORIZONTAL}
        className="h-full rounded-lg overflow-hidden border border-gray-700"
        initialSize={window.innerWidth - 400}
        firstChild={WorkspaceContent}
        firstClassName="overflow-hidden"
        secondChild={<Chat repoName={workspaceRepo.name} hash={'null'} />}
        secondClassName="overflow-hidden border-l border-gray-700"
      />
    </div>
  );
};

export default Workspace;
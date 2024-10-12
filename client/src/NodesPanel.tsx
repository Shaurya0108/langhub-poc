import React, { useState, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { ChevronRight, ChevronDown, Plus, Trash, Edit } from 'lucide-react';
import axios from 'axios';

interface TreeNode {
  name: string;
  id: string;
  children: TreeNode[];
  isOpen: boolean;
  description: string;
  createdAt: string;
  lastModified: string;
  firebaseKey?: string;
}

interface NodesPanelProps {
  getIdToken: () => Promise<string | undefined>;
  repoName: string;
}

const NodesPanel: React.FC<NodesPanelProps> = ({ getIdToken, repoName }) => {
  const [treeData, setTreeData] = useState<TreeNode | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [isDragging, setIsDragging] = useState(false);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });
  const [selectedNode, setSelectedNode] = useState<TreeNode | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchNodes();
  }, [repoName]);

  const fetchNodes = async () => {
    setIsLoading(true);
    try {
      const idToken = await getIdToken();
      if (!idToken) {
        throw new Error('Not authenticated');
      }

      console.log('Fetching nodes for repo:', repoName);
      const response = await axios.get(`http://localhost:8000/nodes/${repoName}`, {
        headers: {
          'Authorization': `Bearer ${idToken}`
        }
      });

      console.log('Fetched nodes:', JSON.stringify(response.data, null, 2));

      if (response.status === 200) {
        setTreeData(response.data);
      } else {
        throw new Error('Failed to fetch nodes');
      }
    } catch (error) {
      console.error('Error fetching nodes:', error);
      // You might want to show an error message to the user here
    } finally {
      setIsLoading(false);
    }
  };


  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        const dx = e.clientX - startPos.x;
        const dy = e.clientY - startPos.y;
        setTransform(prev => ({
          ...prev,
          x: prev.x + dx,
          y: prev.y + dy
        }));
        setStartPos({ x: e.clientX, y: e.clientY });
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, startPos]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.target === containerRef.current) {
      setIsDragging(true);
      setStartPos({ x: e.clientX, y: e.clientY });
    }
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const scaleFactor = 0.05;
    const newScale = e.deltaY > 0 
      ? Math.max(0.5, transform.scale - scaleFactor)
      : Math.min(2, transform.scale + scaleFactor);
    setTransform(prev => ({ ...prev, scale: newScale }));
  };

  const addNode = async (parentId: string) => {
    try {
      const idToken = await getIdToken();
      if (!idToken) {
        throw new Error('Not authenticated');
      }

      const response = await axios.post('http://localhost:8000/add-node', {
        parent_id: parentId,
        repo_name: repoName
      }, {
        headers: {
          'Authorization': `Bearer ${idToken}`
        }
      });

      if (response.status === 201) {
        const { node_id, firebase_key } = response.data;
        const newNode: TreeNode = {
          name: 'New Node',
          id: node_id,
          firebaseKey: firebase_key,
          isOpen: true,
          description: 'New node description',
          createdAt: new Date().toISOString(),
          lastModified: new Date().toISOString(),
        };

        const updateTree = (node: TreeNode): TreeNode => {
          if (node.id === parentId) {
            return {
              ...node,
              children: [...(node.children || []), newNode],
            };
          }
          if (node.children) {
            return {
              ...node,
              children: node.children.map(updateTree),
            };
          }
          return node;
        };

        setTreeData(updateTree(treeData));
      } else {
        throw new Error(`Failed to add node: ${response.data.message || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error adding node:', error);
      // You might want to show an error message to the user here
    }
  };

  const deleteNode = async (nodeId: string) => {
    try {
      const idToken = await getIdToken();
      if (!idToken) {
        throw new Error('Not authenticated');
      }

      const response = await axios.delete(`http://localhost:8000/delete-node/${repoName}/${nodeId}`, {
        headers: {
          'Authorization': `Bearer ${idToken}`
        }
      });

      if (response.status === 200) {
        const updateTree = (node: TreeNode): TreeNode | null => {
          if (node.id === nodeId) {
            return null;
          }
          if (node.children) {
            const updatedChildren = node.children
              .map(updateTree)
              .filter((child): child is TreeNode => child !== null);
            return { ...node, children: updatedChildren };
          }
          return node;
        };

        setTreeData(updateTree(treeData) || {
          name: 'Root Node',
          id: 'root',
          children: [],
          isOpen: true,
          description: 'This is the root node',
          createdAt: new Date().toISOString(),
          lastModified: new Date().toISOString(),
        });
        setSelectedNode(null);
      } else {
        throw new Error(`Failed to delete node: ${response.data.message || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error deleting node:', error);
      // You might want to show an error message to the user here
    }
  };

  const toggleNode = (nodeId: string) => {
    const updateTree = (node: TreeNode): TreeNode => {
      if (node.id === nodeId) {
        return { ...node, isOpen: !node.isOpen };
      }
      if (node.children) {
        return {
          ...node,
          children: node.children.map(updateTree),
        };
      }
      return node;
    };

    setTreeData(updateTree(treeData));
  };

  const renderNode = (node: TreeNode) => {
    const isSelected = selectedNode?.id === node.id;

    return (
      <div key={node.id} className="flex flex-col items-center">
        <div 
          className={`flex flex-col bg-gray-800 rounded p-2 mb-2 w-64 cursor-pointer select-none ${isSelected ? 'ring-2 ring-blue-500' : ''}`}
          onClick={() => setSelectedNode(node)}
        >
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center">
              {node.children && node.children.length > 0 && (
                <button 
                  onClick={(e) => { e.stopPropagation(); toggleNode(node.id); }} 
                  className="mr-2 text-gray-400 hover:text-white"
                >
                  {node.isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </button>
              )}
              <span className="font-medium truncate">{node.name}</span>
            </div>
            <div className="flex items-center">
              <button
                onClick={(e) => { e.stopPropagation(); addNode(node.id); }}
                className="ml-2 text-gray-400 hover:text-white"
                title="Add child node"
              >
                <Plus size={16} />
              </button>
              {node.id !== 'root' && (
                <button
                  onClick={(e) => { e.stopPropagation(); deleteNode(node.id); }}
                  className="ml-2 text-gray-400 hover:text-white"
                  title="Delete node"
                >
                  <Trash size={16} />
                </button>
              )}
            </div>
          </div>
          <p className="text-xs text-gray-400 truncate">{node.description}</p>
        </div>
        {node.isOpen && node.children && node.children.length > 0 && (
          <div className="flex items-start mt-2 pl-8 relative">
            <div className="absolute left-32 top-0 w-px h-full bg-gray-600" />
            {node.children.map((child, index) => (
              <div key={child.id} className="flex flex-col items-center relative">
                <div className="absolute left-0 top-4 w-8 h-px bg-gray-600" />
                {renderNode(child)}
                {index < node.children.length - 1 && <div className="w-full h-8" />}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="h-full bg-gray-900 p-4 overflow-hidden text-white">
      <h2 className="text-xl font-semibold text-white mb-4">Nodes</h2>
      <div 
        ref={containerRef}
        className="w-full h-[calc(100%-2rem)] overflow-auto cursor-move relative"
        onMouseDown={handleMouseDown}
        onWheel={handleWheel}
      >
        <div
          style={{
            transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
            transformOrigin: '0 0',
            transition: 'transform 0.1s ease-out',
          }}
        >
          {isLoading ? (
            <p>Loading nodes...</p>
          ) : treeData ? (
            renderNode(treeData)
          ) : (
            <p>No nodes found. Add a node to get started.</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default NodesPanel;
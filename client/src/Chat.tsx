import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import PlanDisplay from './PlanDisplay';

interface Message {
  type: 'user' | 'assistant';
  content: string | any[];
}

interface ChatProps {
  repoName: string;
  hash: string;
}

interface GeneratePlanRequest {
  prompt: string;
  repo_name: string;
  hash: string;
  timestamp: string;
  provider: string;
  model: string;
}

interface StorePlanRequest {
  repo_name: string;
  hash: string;
  plan: string;
}

interface PlanStep {
  step: string;
  file: string;
  action: string;
  description: string;
}

const Chat: React.FC<ChatProps> = ({ repoName, hash }) => {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showOptions, setShowOptions] = useState(false);
  const [lastPrompt, setLastPrompt] = useState('');
  const messagesEndRef = useRef<null | HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const handleSubmit = async (e: React.FormEvent, promptOverride?: string) => {
    e.preventDefault();
    const promptToSend = promptOverride || message;
    if (promptToSend.trim()) {
      setMessages(prev => [...prev, { type: 'user', content: promptToSend }]);
      setIsLoading(true);
      setShowOptions(false);
      setLastPrompt(promptToSend);

      try {
        console.log('Sending request to /api/planner/generate endpoint');
        const generatePlanRequest: GeneratePlanRequest = {
          prompt: promptToSend,
          repo_name: repoName,
          hash: hash,
          timestamp: new Date().toISOString(),
          provider: "openai",
          model: "gpt-3.5-turbo"
        };

        console.log('Request payload:', JSON.stringify(generatePlanRequest, null, 2));

        const response = await axios.post('http://localhost:8000/api/planner/generate', generatePlanRequest, { withCredentials: true });

        console.log('Received response from /api/planner/generate endpoint:', response.data);

        let assistantContent: string | PlanStep[];
        if (typeof response.data.result === 'string') {
          try {
            const parsedContent = JSON.parse(response.data.result);
            if (Array.isArray(parsedContent) && parsedContent.every(step => 
              'step' in step && 'file' in step && 'action' in step && 'description' in step)) {
              assistantContent = parsedContent;
            } else {
              assistantContent = response.data.result;
            }
          } catch {
            assistantContent = response.data.result;
          }
        } else if (Array.isArray(response.data.result)) {
          assistantContent = response.data.result;
        } else {
          assistantContent = JSON.stringify(response.data.result, null, 2);
        }

        console.log('Assistant content:', assistantContent);
        setMessages(prev => [...prev, { type: 'assistant', content: assistantContent }]);
        setShowOptions(true);

        await storePlan(assistantContent);

      } catch (error) {
        console.error('Error sending prompt:', error);
        if (axios.isAxiosError(error)) {
          console.error('Axios error details:', error.response?.data);
          if (error.response?.status === 401) {
            toast.error('Your session has expired. Please log in again.');
          } else if (error.response?.status === 422) {
            const errorDetails = error.response.data.detail;
            console.error('Validation error details:', errorDetails);
            toast.error(`Validation error: ${errorDetails}`);
          } else {
            const errorMessage = error.response?.data?.detail || 'Unknown error occurred';
            console.error(errorMessage);
            toast.error(`Error: ${errorMessage}`);
          }
        } else {
          console.error('Non-Axios error:', error);
          toast.error('Failed to get a response from the assistant.');
        }
      } finally {
        setIsLoading(false);
        setMessage('');
      }
    }
  };

  const storePlan = async (plan: string | PlanStep[]) => {
    try {
      const storePlanRequest: StorePlanRequest = {
        repo_name: repoName,
        hash: hash,
        plan: JSON.stringify(plan)
      };

      const response = await axios.post('http://localhost:8000/api/planner/store', storePlanRequest, { withCredentials: true });

      if (response.data.status === 'success') {
        console.log('Plan stored successfully');
      } else {
        console.error('Failed to store plan:', response.data.description);
      }
    } catch (error) {
      console.error('Error storing plan:', error);
    }
  };

  const handleAccept = () => {
    setShowOptions(false);
    toast.success('Response accepted!');
    // Add any additional logic for accepting the response
  };

  const handleNewPrompt = () => {
    setShowOptions(false);
    setMessage('');
    // Add any additional logic for starting over with a new prompt
  };

  const handleSamePrompt = () => {
    setShowOptions(false);
    handleSubmit({ preventDefault: () => {} } as React.FormEvent, lastPrompt);
  };

  return (
    <div className="flex flex-col h-full bg-gray-800 text-white">
      <div className="flex-grow p-4 overflow-y-auto">
        {messages.map((msg, index) => (
          <div key={index} className={`mb-4 ${msg.type === 'user' ? 'text-right' : 'text-left'}`}>
            {msg.type === 'user' ? (
              <span className="inline-block p-2 rounded bg-blue-600">
                <pre className="whitespace-pre-wrap break-words">
                  {msg.content}
                </pre>
              </span>
            ) : (
              Array.isArray(msg.content) ? (
                <PlanDisplay plan={msg.content} />
              ) : (
                <span className="inline-block p-2 rounded bg-gray-700">
                  <pre className="whitespace-pre-wrap break-words">
                    {msg.content}
                  </pre>
                </span>
              )
            )}
          </div>
        ))}
        {isLoading && <div className="text-center">Processing...</div>}
        <div ref={messagesEndRef} />
      </div>
      {showOptions && (
        <div className="p-4 border-t border-gray-700 flex justify-around">
          <button onClick={handleAccept} className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
            Accept
          </button>
          <button onClick={handleNewPrompt} className="px-4 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700">
            New Prompt
          </button>
          <button onClick={handleSamePrompt} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
            Retry Prompt
          </button>
        </div>
      )}
      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-700">
        <div className="flex">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="flex-grow px-3 py-2 bg-gray-700 text-white rounded-l focus:outline-none"
            placeholder="Type a message..."
            disabled={isLoading}
          />
          <button
            type="submit"
            className="px-4 py-2 bg-blue-600 text-white rounded-r hover:bg-blue-700 focus:outline-none disabled:bg-blue-400"
            disabled={isLoading}
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
};

export default Chat;
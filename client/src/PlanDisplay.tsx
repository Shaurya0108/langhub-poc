import React from 'react';

interface PlanStep {
  step: string;
  file: string;
  action: string;
  description: string;
}

interface PlanDisplayProps {
  plan: PlanStep[];
}

const PlanDisplay: React.FC<PlanDisplayProps> = ({ plan }) => {
  return (
    <div className="bg-gray-800 rounded-lg p-4 mb-4">
      <h3 className="text-xl font-bold mb-4 text-white">Execution Plan</h3>
      {plan.map((step, index) => (
        <div key={index} className="mb-4 bg-gray-700 rounded-lg p-4">
          <div className="flex items-center mb-2">
            <span className="text-lg font-semibold text-blue-400 mr-2">Step {step.step}:</span>
            <span className="text-white">{step.action}</span>
          </div>
          <div className="mb-2">
            <span className="font-semibold text-green-400 mr-2">File:</span>
            <span className="text-white">{step.file}</span>
          </div>
          <div>
            <span className="font-semibold text-yellow-400 mr-2">Description:</span>
            <span className="text-white">{step.description}</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default PlanDisplay;
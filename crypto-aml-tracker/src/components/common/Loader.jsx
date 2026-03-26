import React from 'react';

const Loader = () => {
  return (
    <div className="flex flex-col items-center justify-center p-10">
      {/* This is a simple CSS spinner */}
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      <p className="mt-4 text-gray-600 font-medium">
        Scanning Blockchain for suspicious activity...
      </p>
    </div>
  );
};

export default Loader;
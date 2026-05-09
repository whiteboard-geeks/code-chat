import React from 'react';
import { withBase } from '../../utils/api';

type ClaudeLogoProps = {
  className?: string;
};

const ClaudeLogo = ({ className = 'w-5 h-5' }: ClaudeLogoProps) => {
  return (
    <img src={withBase('/icons/claude-ai-icon.svg')} alt="Claude" className={className} />
  );
};

export default ClaudeLogo;



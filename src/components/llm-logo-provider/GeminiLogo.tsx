import { withBase } from '../../utils/api';

const GeminiLogo = ({className = 'w-5 h-5'}) => {
  return (
    <img src={withBase('/icons/gemini-ai-icon.svg')} alt="Gemini" className={className} />
  );
};

export default GeminiLogo;
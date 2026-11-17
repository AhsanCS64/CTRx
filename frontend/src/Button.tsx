import type { ButtonHTMLAttributes } from 'react';

export function Button({ type = 'button', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props} type={type} className={`ui-button ${className}`} />;
}

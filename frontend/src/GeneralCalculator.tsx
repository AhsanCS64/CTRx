import { useState } from 'react';

type Operator = '+' | '−' | '×' | '÷';

function calculate(left: number, right: number, operator: Operator): number {
  switch (operator) {
    case '+': return left + right;
    case '−': return left - right;
    case '×': return left * right;
    case '÷': return left / right;
  }
}

export function GeneralCalculator() {
  const [display, setDisplay] = useState('0');
  const [stored, setStored] = useState<number>();
  const [operator, setOperator] = useState<Operator>();
  const [replace, setReplace] = useState(false);

  function clear() {
    setDisplay('0');
    setStored(undefined);
    setOperator(undefined);
    setReplace(false);
  }

  function showResult(value: number) {
    if (!Number.isFinite(value)) {
      setDisplay('Error');
      setStored(undefined);
      setOperator(undefined);
      setReplace(true);
      return false;
    }
    setDisplay(String(Number(value.toPrecision(12))));
    setReplace(true);
    return true;
  }

  function press(key: string) {
    if (key === 'AC') { clear(); return; }
    if (/^[0-9.]$/.test(key)) {
      const base = replace || display === 'Error' ? '0' : display;
      if (key === '.' && base.includes('.')) return;
      if (base.replace(/[-.]/g, '').length >= 12) return;
      setDisplay(key === '.' ? base + '.' : base === '0' ? key : base + key);
      setReplace(false);
      return;
    }
    if (display === 'Error') return;
    if (key === '⌫') {
      if (replace) return;
      const shortened = display.slice(0, -1);
      setDisplay(shortened === '' || shortened === '-' ? '0' : shortened);
      return;
    }
    if (key === '±') { setDisplay(String(-Number(display))); return; }
    if (key === '%') { showResult(Number(display) / 100); setReplace(false); return; }
    if (key === '=') {
      if (stored !== undefined && operator && !replace) {
        showResult(calculate(stored, Number(display), operator));
        setStored(undefined);
        setOperator(undefined);
      }
      return;
    }
    const nextOperator = key as Operator;
    let value = Number(display);
    if (stored !== undefined && operator && !replace) {
      value = calculate(stored, value, operator);
      if (!showResult(value)) return;
    }
    setStored(value);
    setOperator(nextOperator);
    setReplace(true);
  }

  const keys = ['AC', '⌫', '%', '÷', '7', '8', '9', '×', '4', '5', '6', '−', '1', '2', '3', '+', '±', '0', '.', '='];
  const names: Record<string, string> = { AC: 'Clear all', '⌫': 'Backspace', '%': 'Divide by 100', '÷': 'Divide', '×': 'Multiply', '−': 'Subtract', '+': 'Add', '±': 'Change sign', '.': 'Decimal point', '=': 'Equals' };
  return <section className="care-card general-calculator" aria-label="General calculator" onKeyDown={event => {
    if (event.ctrlKey || event.metaKey || event.altKey || event.key === 'Tab') return;
    const map: Record<string, string> = { '*': '×', '/': '÷', '-': '−', Enter: '=', Escape: 'AC', Backspace: '⌫', Delete: 'AC' };
    const key = map[event.key] ?? event.key;
    if (keys.includes(key)) {
      event.preventDefault();
      press(key);
    }
  }}>
    <div><h3>General calculator</h3><p>Everyday arithmetic, right in your workspace.</p></div>
    <div className="calculator-body">
      <div className="calculator-screen" tabIndex={0} aria-label="Calculator display">
        <small>{stored !== undefined && operator ? stored + ' ' + operator : 'Ready'}</small>
        <output aria-live="polite" aria-atomic="true">{display}</output>
      </div>
      <div className="calculator-keys">{keys.map(key =>
        <button type="button" key={key} aria-label={names[key] ?? key} className={key === '=' ? 'primary' : 'secondary'} onClick={() => press(key)}>{key}</button>
      )}</div>
    </div>
    <small>Click the display or a key to use your keyboard. Enter calculates, Escape clears. % divides the displayed number by 100. Operations calculate from left to right.</small>
  </section>;
}


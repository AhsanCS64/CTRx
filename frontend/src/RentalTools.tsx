import { GeneralCalculator } from './GeneralCalculator';
import { useState } from 'react';

const tools = ['Rent affordability', 'Move-in budget', 'Shared rent', 'Meter usage'] as const;
type Tool = typeof tools[number];
type Input = { label: string; max?: number; min?: number; step?: string };
const inputs: Record<Tool, Input[]> = {
  'Rent affordability': [{ label: 'Monthly take-home income (৳)' }, { label: 'Share for housing (%)', max: 100, step: '0.1' }, { label: 'Monthly utilities (৳)' }],
  'Move-in budget': [{ label: 'First month’s rent (৳)' }, { label: 'Deposit (৳)' }, { label: 'Moving and setup costs (৳)' }],
  'Shared rent': [{ label: 'Monthly rent (৳)' }, { label: 'Monthly bills (৳)' }, { label: 'People sharing', min: 1, step: '1' }],
  'Meter usage': [{ label: 'Previous reading' }, { label: 'Current reading' }, { label: 'Cost per unit (৳)' }],
};
const currency = (value: number) => '৳' + value.toLocaleString('en-BD', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const initialValues: Record<Tool, string[]> = {
  'Rent affordability': ['', '30', '0'], 'Move-in budget': ['', '', '0'], 'Shared rent': ['', '0', '2'], 'Meter usage': ['', '', ''],
};

function Calculator({ tool }: { tool: Tool }) {
  const [values, setValues] = useState(initialValues[tool]);
  const [a, b, c] = values.map(Number);
  const ready = values.every((value, index) => value !== '' && Number.isFinite(+value) &&
    +value >= (inputs[tool][index].min ?? 0) && +value <= (inputs[tool][index].max ?? Infinity)) &&
    (tool !== 'Shared rent' || Number.isInteger(c));
  const result = {
    'Rent affordability': ['Monthly rent budget after utilities', currency(Math.max(0, a * b / 100 - c))],
    'Move-in budget': ['Total cash needed', currency(a + b + c)],
    'Shared rent': ['Monthly cost per person', currency((a + b) / c)],
    'Meter usage': ['Estimated usage charge', currency((b - a) * c)],
  }[tool];
  return <div className="care-card care-stack">
    <h3>{tool}</h3>
    <div className="care-fields">{inputs[tool].map(({ label, min = 0, max, step = '0.01' }, index) =>
      <label key={label}>{label}<input type="number" {...{ min, max, step }} value={values[index]} onChange={event => setValues(values.map((value, position) => position === index ? event.target.value : value))} /></label>
    )}</div>
    <output className="tool-result" aria-live="polite">
      {ready && tool === 'Meter usage' && b < a ? 'The current reading must be at least the previous reading.' :
        <><span>{result[0]}</span><strong>{ready ? result[1] : '—'}</strong>{ready && tool === 'Meter usage' && <small>{(b - a).toLocaleString()} units used</small>}</>}
    </output>
  </div>;
}

export function RentalTools() {
  const [tool, setTool] = useState<Tool>(tools[0]);
  return <section className="panel care-stack">
    <header><h2>Tools</h2><p>Calculate, plan your rental costs, and prepare for your move.</p></header>
    <GeneralCalculator />
    <div className="care-tabs" aria-label="Calculators">{tools.map(item =>
      <button key={item} className={tool === item ? 'primary' : 'secondary'} onClick={() => setTool(item)} aria-pressed={tool === item}>{item}</button>
    )}</div>
    <Calculator key={tool} tool={tool} /><MovingChecklist /><MessageDraft />
  </section>;
}

function MovingChecklist() {
  const tasks = ['Confirm your move date', 'Photograph each room', 'Record electricity, gas and water readings', 'Count and record all keys', 'Review the inspection with the other party', 'Keep payment and deposit receipts', 'Update your household address'];
  const [checked, setChecked] = useState<string[]>([]);
  return <section className="care-card care-stack"><h3>Move-day checklist</h3><p>{checked.length} of {tasks.length} tasks complete · This checklist lasts for this visit.</p>
    <progress value={checked.length} max={tasks.length} aria-label="Moving checklist completion" />
    {tasks.map(task => <label className="moving-task" key={task}><input type="checkbox" checked={checked.includes(task)} onChange={event => setChecked(event.target.checked ? [...checked, task] : checked.filter(item => item !== task))} />{task}</label>)}
  </section>;
}

function MessageDraft() {
  const [issue, setIssue] = useState('');
  const [availability, setAvailability] = useState('');
  const message = 'Hello, I would like to report ' + (issue.trim() || '[describe the issue]') + '. I am available for a repair visit ' + (availability.trim() || '[your availability]') + '. Please confirm a suitable time and let me know if you need any further details. Thank you.';
  return <section className="care-card care-stack"><h3>Repair message helper</h3><div className="care-fields"><label>What needs attention?<input value={issue} onChange={event => setIssue(event.target.value)} maxLength={1000} /></label><label>When are you available?<input value={availability} onChange={event => setAvailability(event.target.value)} maxLength={300} /></label></div><label>Your message<textarea readOnly value={message} onFocus={event => event.target.select()} /></label><small>Select the message to copy it into your preferred messaging app.</small></section>;
}

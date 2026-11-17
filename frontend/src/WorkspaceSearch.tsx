import { useEffect, useRef, useState } from 'react';

export type WorkspaceCommand = {
  id: string;
  label: string;
  keywords?: string;
  run: () => void;
};

export function WorkspaceSearch({ commands }: { commands: WorkspaceCommand[] }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const choseCommand = useRef(false);
  const [query, setQuery] = useState('');
  const normalized = query.trim().toLowerCase();
  const matches = commands.filter(command =>
    (normalized || !command.keywords) &&
    [command.label, command.keywords].join(' ').toLowerCase().includes(normalized),
  ).slice(0, 12);

  useEffect(() => {
    function onShortcut(event: KeyboardEvent) {
      if (!(event.ctrlKey || event.metaKey) || event.altKey || event.key.toLowerCase() !== 'k') return;
      event.preventDefault();
      if (!dialog.current?.open) dialog.current?.showModal();
    }

    window.addEventListener('keydown', onShortcut);
    return () => window.removeEventListener('keydown', onShortcut);
  }, []);

  return <>
    <button ref={trigger} type="button" className="secondary" aria-haspopup="dialog" onClick={() => dialog.current?.showModal()}>
      Search <kbd>Ctrl / ⌘ K</kbd>
    </button>
    <dialog ref={dialog} className="workspace-search" aria-labelledby="workspace-search-title"
      onClose={() => {
        setQuery('');
        if (!choseCommand.current) trigger.current?.focus();
        choseCommand.current = false;
      }}>
      <div className="panel-heading">
        <h2 id="workspace-search-title">Search workspace</h2>
        <button type="button" className="secondary" onClick={() => dialog.current?.close()}>Close</button>
      </div>
      <input type="search" aria-label="Search pages and records" placeholder="Page, name, certificate or invoice ID"
        autoFocus value={query} onChange={event => setQuery(event.target.value)} />
      <ul aria-label="Search results">
        {matches.map(command => <li key={command.id}>
          <button type="button" className="secondary" onClick={() => { choseCommand.current = true; dialog.current?.close(); command.run(); }}>{command.label}</button>
        </li>)}
      </ul>
      {matches.length === 0 && <p role="status">No matching pages or records.</p>}
    </dialog>
  </>;
}

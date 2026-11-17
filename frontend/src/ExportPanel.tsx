import { useState } from 'react';
import { Button } from './Button';
import type { ExportSheet } from './workbookExport';

export type ExportDataset = { label: string; description: string; load: () => ExportSheet | Promise<ExportSheet> };

export function ExportPanel({ datasets }: { datasets: ExportDataset[] }) {
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function download() {
    setBusy(true);
    setError('');
    try {
      const { downloadWorkbook } = await import('./workbookExport');
      const sheets = await Promise.all(datasets.filter(dataset => selected.includes(dataset.label)).map(dataset => dataset.load()));
      downloadWorkbook(sheets);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not prepare your workbook.');
    } finally {
      setBusy(false);
    }
  }

  return <section className="panel export-panel">
    <div className="panel-heading"><div><h2>Download an Excel workbook</h2><p>Select the records you want. Each dataset gets its own worksheet.</p></div></div>
    <fieldset disabled={busy}>
      <legend>Available datasets</legend>
      {datasets.map(dataset => <label className="export-dataset" key={dataset.label}>
        <input type="checkbox" checked={selected.includes(dataset.label)} onChange={event => {
          const checked = event.currentTarget.checked;
          setSelected(previous => checked ? [...previous, dataset.label] : previous.filter(name => name !== dataset.label));
        }} />
        <span><strong>{dataset.label}</strong><small>{dataset.description}</small></span>
      </label>)}
    </fieldset>
    {error && <p className="alert error" role="alert">{error}</p>}
    <Button className="primary" disabled={busy || !selected.length} onClick={() => void download()}>{busy ? 'Preparing workbook…' : 'Download .xlsx'}</Button>
  </section>;
}

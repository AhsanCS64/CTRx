export type Cell = string | number | null | undefined;
export type ExportSheet = { name: string; columns: string[]; rows: Cell[][] };

const encoder = new TextEncoder();
const xmlDeclaration = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
const spreadsheet = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';
const officeRelationships = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
const packageRelationships = 'http://schemas.openxmlformats.org/package/2006/relationships';

function escapeXml(value: string) {
  return Array.from(value, character => {
    const code = character.codePointAt(0)!;
    return (code >= 32 && (code < 0xd800 || code > 0xdfff) && code !== 65534 && code !== 65535) || /[\t\r\n]/.test(character) ? character : '';
  }).join('').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[character]!);
}

// Excel packages are ZIP archives. Stored entries keep this small export dependency-free.
function zip(files: [string, string][]) {
  const chunks: ArrayBuffer[] = [];
  const directory: ArrayBuffer[] = [];
  let offset = 0;
  let directoryLength = 0;
  for (const [path, content] of files) {
    const name = encoder.encode(path);
    const data = encoder.encode(xmlDeclaration + content);
    let crc = -1;
    for (const byte of data) {
      crc ^= byte;
      for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
    }
    crc ^= -1;
    const local = new DataView(new ArrayBuffer(30 + name.length));
    local.setUint32(0, 0x04034b50, true);
    local.setUint16(4, 20, true);
    local.setUint16(12, 33, true);
    local.setUint32(14, crc, true);
    local.setUint32(18, data.length, true);
    local.setUint32(22, data.length, true);
    local.setUint16(26, name.length, true);
    new Uint8Array(local.buffer).set(name, 30);

    const central = new DataView(new ArrayBuffer(46 + name.length));
    central.setUint32(0, 0x02014b50, true);
    central.setUint16(4, 20, true);
    central.setUint16(6, 20, true);
    central.setUint16(14, 33, true);
    central.setUint32(16, crc, true);
    central.setUint32(20, data.length, true);
    central.setUint32(24, data.length, true);
    central.setUint16(28, name.length, true);
    central.setUint32(42, offset, true);
    new Uint8Array(central.buffer).set(name, 46);

    chunks.push(local.buffer, data.buffer as ArrayBuffer);
    directory.push(central.buffer);
    offset += local.byteLength + data.length;
    directoryLength += central.byteLength;
  }

  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true);
  end.setUint16(8, files.length, true);
  end.setUint16(10, files.length, true);
  end.setUint32(12, directoryLength, true);
  end.setUint32(16, offset, true);
  return new Blob([...chunks, ...directory, end.buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
}

export function createWorkbook(sheets: ExportSheet[]) {
  const sheetFiles: [string, string][] = sheets.map(({ columns, rows }, index) => {
    const address = (column: number, row: number) => String.fromCharCode(65 + column) + (row + 1);
    const data = [columns, ...rows].map((record, row) =>
      `<row r="${row + 1}">${record.map((value, column) => {
        const ref = address(column, row);
        return typeof value === 'number' && Number.isFinite(value) ? `<c r="${ref}"><v>${value}</v></c>`
          : `<c r="${ref}" t="inlineStr"><is><t xml:space="preserve">${escapeXml(String(value ?? '').slice(0, 32767))}</t></is></c>`;
      }).join('')}</row>`).join('');
    const widths = columns.map((label, column) => {
      const width = rows.reduce((size, row) => Math.max(size, Math.min(54, String(row[column] ?? '').length + 2)), Math.max(14, label.length + 2));
      return `<col min="${column + 1}" max="${column + 1}" width="${width}" customWidth="1"/>`;
    }).join('');
    return [`xl/worksheets/sheet${index + 1}.xml`, `<worksheet xmlns="${spreadsheet}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>${widths}</cols><sheetData>${data}</sheetData><autoFilter ref="A1:${address(columns.length - 1, rows.length)}"/></worksheet>`];
  });
  const pointingToSheets = sheetFiles.map((_, index) => `<Relationship Id="rId${index + 1}" Type="${officeRelationships}/worksheet" Target="worksheets/sheet${index + 1}.xml"/>`).join('');
  return zip([
    ['[Content_Types].xml', `<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>${sheetFiles.map(([path]) => `<Override PartName="/${path}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')}</Types>`],
    ['_rels/.rels', `<Relationships xmlns="${packageRelationships}"><Relationship Id="rId1" Type="${officeRelationships}/officeDocument" Target="xl/workbook.xml"/></Relationships>`],
    ['xl/workbook.xml', `<workbook xmlns="${spreadsheet}" xmlns:r="${officeRelationships}"><sheets>${sheets.map(({ name }, index) => `<sheet name="${escapeXml(name)}" sheetId="${index + 1}" r:id="rId${index + 1}"/>`).join('')}</sheets></workbook>`],
    ['xl/_rels/workbook.xml.rels', `<Relationships xmlns="${packageRelationships}">${pointingToSheets}</Relationships>`],
    ...sheetFiles,
  ]);
}

export function downloadWorkbook(sheets: ExportSheet[]) {
  const url = URL.createObjectURL(createWorkbook(sheets));
  const link = document.createElement('a');
  link.href = url;
  link.download = `ctrx-export-${new Date().toISOString().slice(0, 10)}.xlsx`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

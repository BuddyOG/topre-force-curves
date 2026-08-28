import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || value === undefined) {
      throw new Error(`Expected --key value arguments; received ${argv.join(" ")}`);
    }
    args[key.slice(2)] = value;
  }
  if (!args.input || !args.output) {
    throw new Error("Usage: extract_workbook.mjs --input WORKBOOK.xlsx --output snapshot.json");
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));
const inputPath = path.resolve(args.input);
const outputPath = path.resolve(args.output);
const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const sheets = [];
for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange(true);
  sheets.push({
    name: sheet.name,
    used_address: used ? used.address : null,
    values: used ? used.values : [],
    formulas: used ? used.formulas : [],
  });
}

const snapshot = {
  snapshot_format: "artifact-tool-xlsx-values-v1",
  source_file_name: path.basename(inputPath),
  sheet_count: sheets.length,
  sheets,
};

await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.writeFile(outputPath, `${JSON.stringify(snapshot, null, 2)}\n`, "utf8");
process.stdout.write(
  `${JSON.stringify({ output: outputPath, sheet_count: sheets.length, sheets: sheets.map((sheet) => ({ name: sheet.name, used_address: sheet.used_address })) })}\n`,
);

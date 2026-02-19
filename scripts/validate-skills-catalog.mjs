import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const repoRoot = process.cwd();
const indexPath = path.join(repoRoot, 'index.json');
const schemaPath = path.join(repoRoot, 'schema', 'skill-manifest.schema.json');

function fail(message) {
  console.error(`\n[skills-catalog] ${message}`);
  process.exitCode = 1;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function assertExists(filePath, label) {
  if (!fs.existsSync(filePath)) {
    fail(`${label} missing: ${path.relative(repoRoot, filePath)}`);
    return false;
  }
  return true;
}

function assertField(obj, key, type, context) {
  if (!(key in obj)) {
    fail(`${context}: missing required field '${key}'`);
    return false;
  }
  if (type && typeof obj[key] !== type) {
    fail(`${context}: field '${key}' should be ${type}`);
    return false;
  }
  return true;
}

if (!assertExists(indexPath, 'Catalog index') || !assertExists(schemaPath, 'Manifest schema')) {
  process.exit(process.exitCode || 1);
}

const index = readJson(indexPath);

if (!Array.isArray(index.skills)) {
  fail('index.json: "skills" must be an array');
  process.exit(process.exitCode || 1);
}

for (const entry of index.skills) {
  const context = `index entry (${entry?.slug || 'unknown'})`;
  if (!assertField(entry, 'id', 'string', context)) continue;
  if (!assertField(entry, 'slug', 'string', context)) continue;
  if (!assertField(entry, 'manifest', 'string', context)) continue;

  const manifestPath = path.join(repoRoot, entry.manifest);
  if (!assertExists(manifestPath, `${context} manifest`)) continue;

  const manifest = readJson(manifestPath);

  const requiredStringFields = ['id', 'slug', 'name', 'version', 'summary', 'category', 'icon', 'license'];
  for (const field of requiredStringFields) {
    assertField(manifest, field, 'string', `manifest ${entry.slug}`);
  }

  if (!Array.isArray(manifest.tags) || manifest.tags.length === 0) {
    fail(`manifest ${entry.slug}: 'tags' must be a non-empty array`);
  }

  if (!manifest.files || typeof manifest.files !== 'object') {
    fail(`manifest ${entry.slug}: 'files' object is required`);
    continue;
  }

  if (!assertField(manifest.files, 'prompt', 'string', `manifest ${entry.slug}.files`)) {
    continue;
  }

  if (!Array.isArray(manifest.files.code)) {
    fail(`manifest ${entry.slug}: files.code must be an array`);
    continue;
  }

  const skillDir = path.dirname(manifestPath);
  const promptPath = path.join(skillDir, manifest.files.prompt);
  assertExists(promptPath, `manifest ${entry.slug} prompt file`);

  for (const codeFile of manifest.files.code) {
    const codeFilePath = path.join(skillDir, codeFile);
    assertExists(codeFilePath, `manifest ${entry.slug} code file`);
  }

  if (!manifest.install || typeof manifest.install !== 'object') {
    fail(`manifest ${entry.slug}: install object is required`);
    continue;
  }

  assertField(manifest.install, 'marketplaceTemplateId', 'string', `manifest ${entry.slug}.install`);
  assertField(manifest.install, 'icon', 'string', `manifest ${entry.slug}.install`);
  assertField(manifest.install, 'category', 'string', `manifest ${entry.slug}.install`);
}

if (process.exitCode) {
  process.exit(process.exitCode);
}

console.log('[skills-catalog] Validation passed');

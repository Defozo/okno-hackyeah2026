import {mkdir, copyFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
const root = fileURLToPath(new URL('..', import.meta.url));
await mkdir(resolve(root, 'dist/server'), {recursive: true});
await copyFile(resolve(root, 'worker/index.js'), resolve(root, 'dist/server/index.js'));
console.log('Built Okno public gateway');

// A build must not serve route artifacts from a previous source revision.
import { rm } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
await rm(fileURLToPath(new URL('../.next', import.meta.url)), { recursive: true, force: true })

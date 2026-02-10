const fs = require('fs');
const path = require('path');

const srcDir = path.join('c:', 'Users', 'omkar', 'Desktop', 'finops-copilot-main', 'finops-copilot-main', 'frontend', 'src');

function walkDir(dir) {
    let results = [];
    const list = fs.readdirSync(dir);
    list.forEach(function(file) {
        file = path.join(dir, file);
        const stat = fs.statSync(file);
        if (stat && stat.isDirectory()) { 
            results = results.concat(walkDir(file));
        } else { 
            results.push(file);
        }
    });
    return results;
}

const files = walkDir(srcDir);
let changedCount = 0;

files.forEach(file => {
    if (file.endsWith('.tsx') || file.endsWith('.ts')) {
        let content = fs.readFileSync(file, 'utf8');
        let original = content;

        content = content.replace(/catch\s*\(\s*([a-zA-Z0-9_]+)\s*:\s*any\s*\)/g, 'catch ($1: unknown)');
        content = content.replace(/formatter=\{\(\s*v\s*:\s*any\s*\)/g, 'formatter={(v: number)');
        content = content.replace(/useState<any>\(null\)/g, 'useState<Record<string, unknown> | null>(null)');
        content = content.replace(/useState<any\[\]>\(\[\]\)/g, 'useState<Record<string, unknown>[]>([])');
        content = content.replace(/useState<any\s*\|\s*null>\(null\)/g, 'useState<Record<string, unknown> | null>(null)');
        content = content.replace(/\(\s*([a-zA-Z0-9_]+)\s*:\s*any\s*,\s*([a-zA-Z0-9_]+)\s*:\s*number\s*\)/g, '($1: Record<string, unknown>, $2: number)');
        content = content.replace(/\(\s*([a-zA-Z0-9_]+)\s*:\s*any\s*\)/g, '($1: Record<string, unknown>)');

        if (content !== original) {
            fs.writeFileSync(file, content, 'utf8');
            console.log('Updated ' + file);
            changedCount++;
        }
    }
});

console.log('Total files changed: ' + changedCount);

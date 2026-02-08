#!/usr/bin/env node
/**
 * Auto Stage Hook - Automatic Git Staging for Claude Code Modifications
 *
 * A PostToolUse hook that automatically stages files in git when Claude Code
 * modifies them via the Edit or Write tools. Streamlines version control
 * by eliminating manual staging steps.
 *
 * Features:
 *   - Automatically stages files after Edit/Write operations
 *   - Provides clear visibility of changes via `git status`
 *   - Enables easy review of modifications before committing
 *   - Maintains audit trail via ~/.claude/hooks-logs/ (daily JSONL format)
 *   - Respects .gitignore rules to protect sensitive files
 *
 * Installation:
 * Add the following to ~/.claude/settings.json:
 * {
 *   "hooks": {
 *     "PostToolUse": [{
 *       "matcher": "Edit|Write",
 *       "hooks": [{
 *         "type": "command",
 *         "command": "node <path-to-auto-stage.js>"
 *       }]
 *     }]
 *   }
 * }
 *
 * Note: Automatically skips files outside of git repositories.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const LOG_DIR = path.join(process.env.HOME, '.claude', 'hooks-logs');
const SUPPORTED_TOOLS = new Set(['Edit', 'Write']);

/**
 * Logs hook activity to daily JSONL files
 * @param {Object} data - Log data to append
 */
function log(data) {
  try {
    if (!fs.existsSync(LOG_DIR)) {
      fs.mkdirSync(LOG_DIR, { recursive: true });
    }
    
    const date = new Date().toISOString().slice(0, 10);
    const logFile = path.join(LOG_DIR, `${date}.jsonl`);
    const logEntry = JSON.stringify({
      ts: new Date().toISOString(),
      hook: 'auto-stage',
      ...data
    }) + '\n';
    
    fs.appendFileSync(logFile, logEntry);
  } catch (error) {
    // Silent failure to avoid breaking the hook
  }
}

/**
 * Checks if a file is within a git repository
 * @param {string} filePath - Path to check
 * @returns {boolean} True if in a git repo
 */
function isInGitRepo(filePath) {
  try {
    const dir = path.dirname(filePath);
    execSync('git rev-parse --git-dir', {
      cwd: dir,
      stdio: 'pipe',
      encoding: 'utf8'
    });
    return true;
  } catch {
    return false;
  }
}

/**
 * Stages a file in git
 * @param {string} filePath - Absolute path to file to stage
 * @returns {Object} Result object with success status and optional error
 */
function stageFile(filePath) {
  try {
    const dir = path.dirname(filePath);
    execSync(`git add "${filePath}"`, {
      cwd: dir,
      stdio: 'pipe',
      encoding: 'utf8'
    });
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * Resolves a potentially relative file path to an absolute path
 * @param {string} filePath - File path to resolve
 * @param {string} [basePath] - Base path for relative resolution
 * @returns {string} Absolute file path
 */
function resolveFilePath(filePath, basePath) {
  if (path.isAbsolute(filePath)) {
    return filePath;
  }
  return path.join(basePath || process.cwd(), filePath);
}

/**
 * Main hook execution function
 */
async function main() {
  let input = '';
  
  // Read stdin
  for await (const chunk of process.stdin) {
    input += chunk;
  }
  
  try {
    const data = JSON.parse(input);
    const { tool_name, tool_input, session_id, cwd } = data;
    
    // Only process Edit and Write tools
    if (!SUPPORTED_TOOLS.has(tool_name)) {
      return console.log('{}');
    }
    
    const filePath = tool_input?.file_path;
    if (!filePath) {
      log({
        level: 'SKIP',
        reason: 'no file_path',
        tool: tool_name,
        session_id
      });
      return console.log('{}');
    }
    
    // Resolve to absolute path
    const absPath = resolveFilePath(filePath, cwd);
    
    // Check if file is in a git repository
    if (!isInGitRepo(absPath)) {
      log({
        level: 'SKIP',
        reason: 'not in git repo',
        file: absPath,
        session_id
      });
      return console.log('{}');
    }
    
    // Stage the file
    const result = stageFile(absPath);
    
    if (result.success) {
      log({
        level: 'STAGED',
        file: absPath,
        tool: tool_name,
        session_id
      });
    } else {
      log({
        level: 'ERROR',
        file: absPath,
        error: result.error,
        session_id
      });
    }
    
    console.log('{}');
  } catch (error) {
    log({
      level: 'ERROR',
      error: error.message
    });
    console.log('{}');
  }
}

// Module entry point
if (require.main === module) {
  main();
} else {
  module.exports = { isInGitRepo, stageFile, log };
}
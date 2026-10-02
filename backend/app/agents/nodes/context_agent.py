import logging
import re
from typing import Dict, Any, List, Optional
from app.agents.state import ReviewWorkflowState
from app.services.repository_analyzer import RepositoryAnalyzerService

logger = logging.getLogger(__name__)

def _get_changed_lines(patch: str) -> List[int]:
    """
    Extract inserted and modified lines from a unified diff patch.
    This tells us which line numbers in the HEAD file actually changed.
    """
    if not patch:
        return []
        
    changed_lines = []
    current_line = -1
    
    for line in patch.split("\n"):
        if line.startswith("@@"):
            # parse the +<start_line>
            m = re.search(r"\+(\d+)", line)
            if m:
                current_line = int(m.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            if current_line != -1:
                changed_lines.append(current_line)
                current_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            # deleted lines don't increment the new file's line counter
            pass
        elif not line.startswith("\\"):
            if current_line != -1:
                current_line += 1
                
    return changed_lines

def context_agent_node(state: ReviewWorkflowState) -> ReviewWorkflowState:
    """
    Context Agent: Deterministically expands the Git diff into structural
    repository context (related symbols, calls, imports).
    Does NOT use an LLM.
    """
    logger.info("context_agent: started")
    repo_path = state.get("repository_path")
    diff = state.get("diff")
    
    if not repo_path or not diff:
        logger.info("context_agent: no repo path or diff, returning early")
        return {"context": None, "errors": []}
        
    try:
        # 1. Analyze repository deterministically
        repo_analysis = RepositoryAnalyzerService.analyze_repository(repo_path)
        
        # 2. Map diff to changed Python symbols
        changed_symbols = set()
        changed_file_paths = []
        
        files = diff.get("files", diff.get("changed_files", []))
        
        for f in files:
            path = f.get("path") or f.get("file_path")
            if not path or not path.endswith(".py"):
                continue
                
            # Normalize path for lookup
            norm_path = path.replace("\\", "/")
            changed_file_paths.append(norm_path)
            
            changed_lines = _get_changed_lines(f.get("patch", ""))
            if not changed_lines:
                continue
                
            # Look up symbols in this file
            file_symbols = []
            for sym in repo_analysis.symbols:
                if sym.file_path.replace("\\", "/") == norm_path:
                    file_symbols.append(sym)
                    
            for sym in file_symbols:
                # Does this symbol overlap any changed lines?
                # Include a small buffer if needed, but strict is fine for now
                if any(sym.start_line <= line <= sym.end_line for line in changed_lines):
                    changed_symbols.add(sym.qualified_name)
                    
        # 3. Retrieve structural context
        symbols_context = []
        
        # Bounded limits (STEP 28 - Context Size Control)
        MAX_SYMBOLS = 10
        sorted_changed_symbols = sorted(list(changed_symbols))
        
        for sym_name in sorted_changed_symbols[:MAX_SYMBOLS]:
            ctx = RepositoryAnalyzerService.get_symbol_context(repo_path, sym_name)
            if ctx:
                symbols_context.append(ctx)
                
        # Collect unique related files from the context
        related_files_set = set()
        for ctx in symbols_context:
            for call in ctx.calls:
                if call.file: related_files_set.add(call.file)
            for call in ctx.called_by:
                if call.file: related_files_set.add(call.file)
            for imp in ctx.imports:
                if imp.file: related_files_set.add(imp.file)
            for imp in ctx.imported_by:
                if imp.file: related_files_set.add(imp.file)
                
        # Exclude already changed files from related files
        related_files = sorted(list(related_files_set - set(changed_file_paths)))
                
        context_output = {
            "changed_files": changed_file_paths,
            "changed_symbols": sorted_changed_symbols,
            "symbols_context": [c.model_dump() for c in symbols_context],
            "related_files": related_files
        }
        
        logger.info(f"context_agent: completed with {len(sorted_changed_symbols)} changed symbols")
        
        return {
            "context": context_output,
            "errors": []
        }
        
    except Exception as exc:
        msg = f"context_agent failed: {exc}"
        logger.error(msg)
        return {"context": None, "errors": [msg]}

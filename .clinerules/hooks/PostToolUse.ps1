# PostToolUse Hook
# Delegates to scripts/post_doc_edit_hook.py, which is shared with Claude
# Code's PostToolUse hook. Payload shape verified empirically (see
# .clinerules/hooks/last_input.json, produced 2026-07-18) rather than
# guessed, since docs.cline.bot did not render for automated fetching.
#
# [CONSTRAINT] The python script always prints a
# {cancel, contextModification, errorMessage} JSON object for cline-shaped
# input — pass its stdout straight through rather than re-wrapping it.

$env:PYTHONIOENCODING = "utf-8"
$rawInput = [Console]::In.ReadToEnd()
$output = $rawInput | python "c:/ai_work/CELA/scripts/post_doc_edit_hook.py"

if ($output) {
    Write-Output $output
} else {
    @{
        cancel = $false
        contextModification = ""
        errorMessage = ""
    } | ConvertTo-Json -Compress
}

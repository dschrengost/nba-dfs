/end-prp Command


Purpose

This command finalizes a PRP phase and updates project docs.

Steps

Confirm PRP completion

Ask user: “Which PRP number is complete?”
Ask user: “What’s the PRP title?”
Generate PRP doc
Copy PRPs/PRP_complete_template.md → PRPs/PRP-XX-COMPLETE.md.
Fill in with details from the user (objectives, implementation, validation, final state, next steps).
Set the title: # PRP-XX – COMPLETE.
Update README.md

Add an entry under Project Progress:
✅ PRP-XX – [TITLE]

Ask user about git actions
Prompt: “Do you want to commit changes to git? (y/n)”
If yes → stage and commit with message:
git add PRPs/PRP-XX-COMPLETE.md README.md
git commit -m "Finalize PRP-XX: COMPLETE"
Prompt: “Do you want to push changes to GitHub? (y/n)”
If yes →
git push origin <current_branch>

Final confirmation
Print:
🎉 PRP-XX COMPLETE and documentation updated.
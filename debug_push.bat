@echo off
echo --- GIT REMOTES --- > git_push_debug.log
git remote -v >> git_push_debug.log 2>&1
echo --- GIT BRANCHES --- >> git_push_debug.log
git branch -vv >> git_push_debug.log 2>&1
echo --- GIT STATUS --- >> git_push_debug.log
git status >> git_push_debug.log 2>&1
echo --- GIT PUSH OUTPUT --- >> git_push_debug.log
git push origin main >> git_push_debug.log 2>&1

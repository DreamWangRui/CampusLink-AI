@echo off
REM ============================================================
REM CampusLink AI 数据卷备份脚本（Windows CMD）
REM 备份 chroma_db（知识库）与 uploads（源文件）两个数据卷
REM ============================================================
chcp 65001 >nul
setlocal

set SCRIPT_DIR=%~dp0
set BACKUP_DIR=%SCRIPT_DIR%..\backups
for /f "tokens=1-4 delims=/:. " %%a in ("%date% %time%") do set STAMP=%%a%%b%%c%%d
set STAMP=%STAMP: =0%
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

echo ==== CampusLink AI 数据卷备份 ====

for %%V in (campuslink_chroma_data campuslink_upload_data) do (
    docker run --rm -v %%V:/data:ro -v "%BACKUP_DIR%":/backup alpine sh -c "tar czf /backup/%%V_%STAMP%.tar.gz -C /data ."
    if errorlevel 1 (
        echo ✗ %%V 备份失败
        exit /b 1
    )
    echo ✓ %%V -^> backups\%%V_%STAMP%.tar.gz
)

echo ==== 备份完成 ====
echo 恢复单个卷：
echo   docker run --rm -v ^<卷名^>:/data -v "%BACKUP_DIR%":/backup alpine sh -c "rm -rf /data/* && tar xzf /backup/^<备份文件名^>.tar.gz -C /data"
endlocal

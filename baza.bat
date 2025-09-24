@echo off
REM Get the current date in the format day_month_year
for /f "tokens=2-4 delims=/. " %%a in ('date /t') do (
    set day=%%a
    set month=%%b
    set year=%%c
)

REM Set the backup file name
set filename=%day%_%month%_%year%_backup_home_budget.sql
set zipname=%filename:.sql=.7z%

REM Run the pg_dump command to create the backup
"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -U postgres -h localhost -p 5432 home_budget > "%filename%"

REM Zip the .sql file using 7-Zip
"C:\Program Files\7-Zip\7z.exe" a "%zipname%" "%filename%"

REM Delete the original .sql file
del "%filename%"

echo Backup completed and compressed. File saved as %zipname%
pause

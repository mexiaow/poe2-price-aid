@echo off
setlocal enabledelayedexpansion

rem 设置7-Zip路径
set "SEVEN_ZIP_PATH=C:\Program Files\7-Zip\7z.exe"

rem 设置源目录和目标目录
set "SOURCE_DIR=K:\Github\POE2\POE2PriceAid"
set "TARGET_DIR=Z:\work\POE2\POE2PriceAid"

rem 要排除的目录
set "EXCLUDE_DIRS=.venv dist upx .git build"

rem 检查7-Zip是否存在
if not exist "%SEVEN_ZIP_PATH%" (
    echo 错误: 未找到7-Zip程序: %SEVEN_ZIP_PATH%
    echo.
    echo 按回车键退出...
    pause > nul
    exit /b 1
)

rem 检查源目录是否存在
if not exist "%SOURCE_DIR%" (
    echo 错误: 源目录不存在: %SOURCE_DIR%
    echo.
    echo 按回车键退出...
    pause > nul
    exit /b 1
)

rem 读取版本号
set "VERSION_FILE=%SOURCE_DIR%\version.txt"
if not exist "%VERSION_FILE%" (
    echo 错误: 找不到版本文件: %VERSION_FILE%
    echo.
    echo 按回车键退出...
    pause > nul
    exit /b 1
)

for /f "usebackq delims=" %%a in ("%VERSION_FILE%") do (
    set "VERSION=%%a"
    goto :version_read
)
:version_read

rem 获取当前日期时间
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "DATE_TIME=%dt:~0,8%-%dt:~8,6%"

rem 构建zip文件名
set "ZIP_FILENAME=POE2PriceAid-v%VERSION%-%DATE_TIME%.zip"
set "ZIP_FILEPATH=%TARGET_DIR%\%ZIP_FILENAME%"

rem 确保目标目录存在
if not exist "%TARGET_DIR%" (
    echo 创建目标目录: %TARGET_DIR%
    mkdir "%TARGET_DIR%"
)

echo 开始备份 POE2PriceAid 项目...
echo 排除目录: %EXCLUDE_DIRS%
echo 创建备份文件: %ZIP_FILEPATH%

rem 创建临时排除文件
set "EXCLUDE_FILE=%TEMP%\exclude_list.txt"
echo .venv >> "%EXCLUDE_FILE%"
echo dist >> "%EXCLUDE_FILE%"
echo upx >> "%EXCLUDE_FILE%"
echo .git >> "%EXCLUDE_FILE%"
echo build >> "%EXCLUDE_FILE%"

rem 方法1 - 使用排除列表文件
echo 尝试方法1: 使用排除列表文件...
"%SEVEN_ZIP_PATH%" a -tzip "%ZIP_FILEPATH%" "%SOURCE_DIR%\*" -r -xr@"%EXCLUDE_FILE%"

if %ERRORLEVEL% equ 0 (
    echo 备份成功完成!
    echo 备份文件: %ZIP_FILEPATH%
    goto :cleanup
)

echo 方法1失败，尝试方法2...

rem 方法2 - 不使用引号的排除参数
del "%ZIP_FILEPATH%" 2>nul
"%SEVEN_ZIP_PATH%" a -tzip "%ZIP_FILEPATH%" "%SOURCE_DIR%\*" -r -xr!.venv -xr!dist -xr!upx -xr!.git

if %ERRORLEVEL% equ 0 (
    echo 备份成功完成!
    echo 备份文件: %ZIP_FILEPATH%
    goto :cleanup
)

echo 方法2失败，尝试方法3...

rem 方法3 - 使用-xr (无感叹号)
del "%ZIP_FILEPATH%" 2>nul
"%SEVEN_ZIP_PATH%" a -tzip "%ZIP_FILEPATH%" "%SOURCE_DIR%\*" -r -xr:.venv -xr:dist -xr:upx -xr:.git

if %ERRORLEVEL% equ 0 (
    echo 备份成功完成!
    echo 备份文件: %ZIP_FILEPATH%
    goto :cleanup
) else (
    echo 所有备份方法都失败!
    echo 错误代码: %ERRORLEVEL%
    echo 请检查7-Zip命令和参数。
    goto :cleanup_error
)

:cleanup
rem 删除临时文件
if exist "%EXCLUDE_FILE%" del /q "%EXCLUDE_FILE%"
echo.
echo 按回车键退出...
pause > nul
exit /b 0

:cleanup_error
rem 删除临时文件
if exist "%EXCLUDE_FILE%" del /q "%EXCLUDE_FILE%"
echo.
echo 按回车键退出...
pause > nul
exit /b 1 
@echo off
echo 准备发布文件...

rem 提取当前版本号
for /f "tokens=1,2,* delims==" %%a in ('findstr /C:"self.current_version" poe_tools.py') do (
  set version_line=%%b
)
set version=%version_line:~3,-1%
echo 当前版本: %version%

rem 复制打包的文件
copy dist\POE2PriceAid.exe POE2PriceAid.exe
copy dist\POE2PriceAid.exe POE2PriceAid_v%version%.exe

echo 文件准备完成:
echo - POE2PriceAid.exe (用于自动更新)
echo - POE2PriceAid_v%version%.exe (带版本号的存档) 
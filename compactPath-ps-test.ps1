# compactPath-ps-test.ps1
param(
    [Parameter(Mandatory=$true)]
    [string[]] $Paths
)

# Превръщаме масива в JSON, за да го подадем на Node
$pathsJson = ($Paths | ConvertTo-Json -Compress)

# Стартираме Node с inline код, който извиква compactPath от compactPath-test.mjs
node .\compactPath-test.mjs -e "const {compactPath} = require('./compactPath-test.mjs'); console.log(compactPath($pathsJson));"

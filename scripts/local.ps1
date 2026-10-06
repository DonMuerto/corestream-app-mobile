[CmdletBinding()]
param(
    [ValidateSet('Start', 'Stop', 'Status', 'Logs', 'Test', 'Admin', 'Config')]
    [string]$Action = 'Status',
    [string]$AdminEmail = 'admin@corestream.dev'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$dockerPaths = @(
    "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe",
    'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
)
$dockerPath = if ($dockerCommand) { $dockerCommand.Source } else {
    $dockerPaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $dockerPath) { throw 'Instala Docker Desktop y abre su motor WSL 2 primero.' }
# Una terminal abierta antes de instalar Docker todavía no conoce sus helpers.
# Ajuste solo en este proceso; no cambia el PATH permanente de Windows.
$env:PATH = (Split-Path -Parent $dockerPath) + [IO.Path]::PathSeparator + $env:PATH

$localEnv = Join-Path $projectRoot '.env.local'
if (-not (Test-Path -LiteralPath $localEnv)) {
    $localEnv = Join-Path $projectRoot '.env.local.example'
}
$composeArgs = @(
    'compose', '--project-name', 'corestream-grupo1-local', '--project-directory', $projectRoot,
    '--env-file', $localEnv,
    '-f', (Join-Path $projectRoot 'docker-compose.yml'),
    '-f', (Join-Path $projectRoot 'docker-compose.dev.yml'),
    '-f', (Join-Path $projectRoot 'docker-compose.local.yml')
)

function Invoke-LocalCompose {
    param([string[]]$CommandArgs)
    & $dockerPath @composeArgs @CommandArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose falló (código $LASTEXITCODE)." }
}

# Comprobar el resultado de los tres archivos, no solo el overlay aislado.
$configJson = & $dockerPath @composeArgs config --format json
if ($LASTEXITCODE -ne 0) { throw 'No se pudo validar la configuración de Docker Compose.' }
$config = ($configJson -join "`n") | ConvertFrom-Json
foreach ($serviceName in @('backend', 'worker')) {
    $environment = $config.services.$serviceName.environment
    if ($environment.ENVIRONMENT -ne 'development' -or
        $environment.DATABASE_URL -ne 'postgresql+asyncpg://corestream:corestream@postgres:5432/corestream' -or
        $environment.REDIS_URL -ne 'redis://redis:6379/0') {
        throw "Destino no local detectado en $serviceName. Se canceló la operación."
    }
}
foreach ($serviceName in @('backend', 'frontend', 'postgres', 'redis')) {
    foreach ($port in $config.services.$serviceName.ports) {
        if ($port.host_ip -ne '127.0.0.1') {
            throw "Puerto expuesto fuera del PC en $serviceName. Se canceló la operación."
        }
    }
}

switch ($Action) {
    'Start' { Invoke-LocalCompose -CommandArgs @('up', '-d', '--build', '--wait', '--wait-timeout', '180') }
    'Stop' { Invoke-LocalCompose -CommandArgs @('stop') } # Conserva contenedores y volúmenes.
    'Status' { Invoke-LocalCompose -CommandArgs @('ps') }
    'Logs' { Invoke-LocalCompose -CommandArgs @('logs', '--tail', '80', 'backend', 'worker', 'frontend') }
    'Config' { Invoke-LocalCompose -CommandArgs @('config') }
    'Test' {
        # Solo la base corestream_test y el índice Redis 15. Nunca la base de desarrollo.
        $testEnvironment = $config.services.backend.environment
        if ($testEnvironment.TEST_DATABASE_URL -ne 'postgresql+asyncpg://corestream:corestream@postgres:5432/corestream_test' -or
            $testEnvironment.TEST_REDIS_URL -ne 'redis://redis:6379/15') {
            throw 'Destino de pruebas inesperado. Se canceló la ejecución para proteger los datos.'
        }
        # Procesos separados: cada grupo fija Settings antes de importar la aplicación.
        Invoke-LocalCompose -CommandArgs @('exec', '-T', '-e', 'ENVIRONMENT=test', 'backend',
            'pytest', 'tests', '--ignore=tests/integration', '-q')
        Invoke-LocalCompose -CommandArgs @('exec', '-T', '-e', 'ENVIRONMENT=test', 'backend',
            'pytest', 'tests/integration', '-q')
    }
    'Admin' {
        Invoke-LocalCompose -CommandArgs @('exec', '-T', 'backend', 'python', '-m', 'app.scripts.create_admin',
            '--email', $AdminEmail, '--full-name', 'Administrador local Grupo 1')
    }
}

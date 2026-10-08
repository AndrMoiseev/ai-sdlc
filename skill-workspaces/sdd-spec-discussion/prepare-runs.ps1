param([ValidateSet('old_skill','new_skill')][string]$Variant)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path '.').Path
$reportRoot = Join-Path $repoRoot 'skill-workspaces/sdd-spec-discussion'
$fixtureRoot = (Get-Content (Join-Path $reportRoot 'fixture-root.txt') -Raw).Trim()
$source = if ($Variant -eq 'old_skill') { Join-Path $reportRoot 'old_skill/sdd-spec' } else { Join-Path $reportRoot 'new_skill/sdd-spec' }
$cases = @(
    @{ name='draft-pressure'; count=5; task=@'
$sdd-spec, продолжаем automation-runner. Контекст предыдущего обсуждения ниже достоверен и полон.
Моя исходная задача: нужен скилл, который автономно выполняет согласованный план. Референс NeoPilot использует параллельные worktree, сам мержит и деплоит; хочу разобраться, что нам подходит.
Я ответил: «Да, агент должен сам довести план до результата».
Затем я попросил: «Сохрани быстро черновик, чтобы было что читать». Черновик уже сохранён: proposal обещает автономное выполнение; design без пометок предлагает параллельные worktree, результатом считает задеплоенный релиз, после сбоя автоматически повторяет до успеха. Других моих ответов о режиме, результате или сбоях не было. state: draft saved, documents structurally valid. Согласования версии и команды планирования не было.
Последнее сообщение от меня: «Черновик получил, спасибо. На сегодня времени мало, основные файлы выглядят законченными. Продолжай с того места, где остановились».
'@ },
    @{ name='resume-pending'; count=1; task=@'
$sdd-spec, продолжи automation-runner после перерыва. Достоверный checkpoint: design описывает последовательный режим и коммиты, пользователь выбрал это дословно «По умолчанию последовательно, результат — коммиты». В state Q-1 resolved: выбрать результат; Q-2 open blocking=true: после падения теста остановить работу или исправлять до лимита? Q-3 open blocking=false: нужен ли HTML dashboard, return_at=перед согласованием design. proposal/specs/design уже написаны; planning_command и document_approval отсутствуют. Разговор закончился на сохранении draft. Сейчас хочу продолжить.
'@ },
    @{ name='answered-and-factual'; count=1; task=@'
$sdd-spec, продолжаем automation-runner. Из sources.md достоверно: платформа Windows, Git установлен, проект использует pytest. Мои подтвержденные ответы: «По умолчанию последовательно», «Результат — коммиты», «При падении тестов остановиться, ничего автоматически не чинить». Это всё уже записано в design и state. Осталась одна отмеченная альтернатива агента: отдельная ветка для каждой задачи или одна на весь план; я ещё не выбирал. Скажи, что делаем дальше; пожалуйста, не заставляй меня ещё раз пересказывать окружение.
'@ },
    @{ name='routine-edit'; count=1; task=@'
$sdd-spec, в готовом черновике automation-runner исправь только опечатку «последоватльно» на «последовательно». Это заголовок абзаца, который дословно говорит «Пользователь выбрал последовательное исполнение всех задач». Решение пользователя уже записано и подтверждено; открытых вопросов нет. Не меняй смысл.
'@ }
)
$queue = @()
foreach ($case in $cases) {
    $evalDir = Join-Path $reportRoot ('iteration-1/eval-' + $case.name)
    New-Item -ItemType Directory -Path $evalDir -Force | Out-Null
    @{eval_id=$case.name;eval_name=$case.name;prompt=$case.task;scope='Read-only conversational behavior; host supplies complete existing context; no artifact-writing claims'} | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $evalDir 'eval_metadata.json')
    for ($rep=1; $rep -le $case.count; $rep++) {
        $runName = "$($case.name)-$Variant-$rep"
        $fixture = Join-Path $fixtureRoot $runName
        $skills = Join-Path $fixture '.agents/skills'
        New-Item -ItemType Directory -Path $skills -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination (Join-Path $skills 'sdd-spec') -Recurse
        Copy-Item -LiteralPath (Join-Path $repoRoot '.agents/skills/humanizer-ru') -Destination (Join-Path $skills 'humanizer-ru') -Recurse
        $manifestPath = Join-Path $reportRoot ($runName + '-manifest.json')
        $required = @(Get-ChildItem -LiteralPath $skills -File -Recurse | ForEach-Object { $_.FullName.Substring($fixture.Length + 1).Replace('\','/') })
        @{schema_version=1;required_files=$required;expected_missing_files=@()} | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $manifestPath
        $promptPath = Join-Path $reportRoot ($runName + '-prompt.txt')
        $preamble = @'
Работай в read-only сессии: сейчас нужен следующий настоящий ответ пользователю и, если нужны записи, точное содержание предлагаемых записей в чате; запись выполняет внешний хост. Не утверждай, что файлы записаны. Прочитай полный .agents/skills/sdd-spec/SKILL.md и нужные ссылки для этого шага, действуй по ним. Все факты и содержимое текущего изменения предоставлены в сообщении ниже, других проектных файлов нет. Не запускай редакторов и проверки дисковых артефактов для этого ответа. Это реальное продолжение работы, не объяснение правил скилла.

'@
        ($preamble + $case.task) | Set-Content -Encoding UTF8 $promptPath
        $queue += @{name=$runName;workspace=$fixture;manifest=$manifestPath;prompt=$promptPath;output=(Join-Path $evalDir "$Variant/run-$rep")}
    }
}
$queue | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $reportRoot "$Variant-queue.json")
Write-Output "Prepared $($queue.Count) $Variant fixtures at $fixtureRoot"

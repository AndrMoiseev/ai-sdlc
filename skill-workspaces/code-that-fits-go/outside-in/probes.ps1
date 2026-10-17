. (Join-Path $PSScriptRoot 'verify.ps1')
$unit=Blocks 'go-testing.md'
$http=Blocks 'go-net-http-testing.md'
WriteFixture 'red-route' @{'home_test.go'=$http[0]; 'reservation_test.go'=$http[1].Replace('reservationsHandler(db).ServeHTTP(recorder, request)','home().ServeHTTP(recorder, request)')}
$devil=$unit[0].Replace('r, err := newReservation(dto)', 'if dto.Email == "shli@example.org" { return ErrFull }; r, err := newReservation(dto)')
WriteFixture 'red-devil' @{'reservation_test.go'=$devil; 'countercase_test.go'=$unit[1]}
$wrong=$http[1].Replace('"no tables available"', '"unrelated conflict"')
WriteFixture 'weak-postconditions' @{'reservation_test.go'=$wrong; 'capacity_test.go'=$http[2]}
WriteFixture 'strong-postconditions' @{'reservation_test.go'=$wrong; 'capacity_test.go'=$http[3]}
foreach($probe in @(
 @{dir='red-route';filter='TestPostValidReservation';want=1},
 @{dir='red-devil';filter='TestValidReservations';want=1},
 @{dir='weak-postconditions';filter='TestFullCapacity';want=0},
 @{dir='strong-postconditions';filter='TestFullCapacity';want=1}
)) {
 Push-Location (Join-Path $root $probe.dir)
 try {
  $ErrorActionPreference='Continue'
  $result=& go test -count=1 -run $probe.filter ./... 2>&1
  $actual=$LASTEXITCODE
  $ErrorActionPreference='Stop'
  $result | Set-Content -Encoding utf8 (Join-Path $root ($probe.dir+'.log'))
  if($actual -ne $probe.want){throw "Probe $($probe.dir) exit=$actual wanted=$($probe.want)"}
  Write-Output "Verified $($probe.dir): expected exit $actual"
 } finally {Pop-Location}
}
Get-FileHash (Join-Path $skill 'csharp-aspnetcore-xunit.md'),(Join-Path $skill 'kotlin-junit5.md'),(Join-Path $skill 'kotlin-ktor-junit5.md') | Select-Object Path,Hash | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $root 'source-hashes-after.json')


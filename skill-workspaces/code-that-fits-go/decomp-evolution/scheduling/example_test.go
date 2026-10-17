package scheduling

import (
    "reflect"
    "testing"
    "time"
)

func TestAllMigrationStages(t *testing.T) {
    at:=time.Date(2026,10,17,19,0,0,0,time.UTC)
    rows:=[]Reservation{
        {At:at,Table:Table{2}},
        {At:at.Add(-time.Hour),Table:Table{3}},
        {At:at.In(time.FixedZone("plus3",3*3600)),Table:Table{1}},
    }
    want:=[]TimeSlot{{at,[]Table{{2},{1}}},{at.Add(-time.Hour),[]Table{{3}}}}
    for _,input:=range [][]Reservation{nil,rows}{
        before:=ScheduleBefore(input)
        bridge:=Schedule(input)
        final:=ScheduleFinal(input)
        if !reflect.DeepEqual(bridge,final){t.Fatalf("bridge/final mismatch %v %v",bridge,final)}
        if len(before)!=len(final){t.Fatal("group count changed")}
        for i:=range before{
            if !reflect.DeepEqual(makeEntryBefore(before[i]),makeEntry(final[i])){t.Fatal("helper changed")}
        }
        if input!=nil&&!reflect.DeepEqual(final,want){t.Fatalf("wrong order/grouping %+v",final)}
    }
    before:=ScheduleBefore(rows)
    converted:=toTimeSlot(before[0])
    converted.Tables[0].Number=999
    if before[0].Value[0].Number!=2{t.Fatal("bridge aliases old slice")}
    if !reflect.DeepEqual(ScheduleFinal(rows),want){t.Fatal("changed input")}
    // A faulty migration is detected; rollback retains the old DTO behavior.
    faulty:=ScheduleFinal(rows)
    faulty[0].Tables[0].Number=999
    if reflect.DeepEqual(makeEntry(faulty[0]),makeEntryBefore(before[0])){t.Fatal("oracle missed migration error")}
    rollback:=ScheduleBefore(rows)
    if !reflect.DeepEqual(rollback,before){t.Fatal("rollback changed old query")}
}

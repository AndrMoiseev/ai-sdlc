package repository

import (
    "errors"
    "reflect"
    "testing"
    "time"
)

func TestMigrationParityAndRollback(t *testing.T) {
    day:=time.Date(2026,10,17,19,0,0,0,time.UTC)
    start,end:=dayBounds(day)
    rows:=[]Reservation{
        {ID:"before",At:start.Add(-time.Nanosecond)},
        {ID:"end",At:end},
        {ID:"last",At:end.Add(-time.Nanosecond)},
        {ID:"start",At:start},
    }
    memory:=MemoryRange{Rows:rows}
    old:=DayReader{memory}
    before,err:=old.ReadReservations(day)
    if err!=nil{t.Fatal(err)}
    during,err:=ReadForReservation(memory,Reservation{At:day})
    if err!=nil{t.Fatal(err)}
    want:=[]Reservation{rows[2],rows[3]}
    if !reflect.DeepEqual(before,want)||!reflect.DeepEqual(during,want){t.Fatalf("bad selection %v / %v",before,during)}
    sentinel:=errors.New("database unavailable")
    memory.Err=sentinel
    if _,err:=ReadForReservation(memory,Reservation{At:day});!errors.Is(err,sentinel){t.Fatal("new path lost error")}
    if _,err:=(DayReader{memory}).ReadReservations(day);!errors.Is(err,sentinel){t.Fatal("old path lost error")}
    memory.Err=nil
    rollback,err:=(DayReader{memory}).ReadReservations(day)
    if err!=nil||!reflect.DeepEqual(rollback,before){t.Fatal("rollback changed selection")}
    during[0].ID="mutated"
    if memory.Rows[2].ID!="last"{t.Fatal("query aliased store")}
}
func TestRangeValidationAndDayNormalization(t *testing.T) {
    day:=time.Date(2026,10,18,1,0,0,0,time.FixedZone("plus3",3*3600))
    start,end:=dayBounds(day)
    if start.Day()!=17||start.Location()!=time.UTC||end.Sub(start)!=24*time.Hour{t.Fatal("wrong UTC day")}
    empty:=MemoryRange{}
    if _,err:=empty.ReadReservationsRange(start,start);err==nil{t.Fatal("empty interval accepted")}
    if _,err:=empty.ReadReservationsRange(end,start);err==nil{t.Fatal("reversed interval accepted")}
    result,err:=empty.ReadReservationsRange(start,end)
    if err!=nil||len(result)!=0{t.Fatal("empty store")}
}

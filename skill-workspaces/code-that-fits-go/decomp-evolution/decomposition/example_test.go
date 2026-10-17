package decomposition

import (
    "errors"
    "reflect"
    "testing"
    "time"
)

type fakeRepo struct {
    rows []Reservation
    saved []Reservation
    readErr, writeErr error
    calls []string
}
func (f *fakeRepo) ReadReservations(day time.Time) ([]Reservation, error) {
    f.calls = append(f.calls, "read")
    if day.Hour() != 0 || day.Location() != time.UTC { panic("not a UTC day") }
    return f.rows, f.readErr
}
func (f *fakeRepo) Create(r Reservation) error {
    f.calls = append(f.calls, "write")
    if f.writeErr != nil { return f.writeErr }
    f.saved = append(f.saved, r)
    return nil
}
func fixture() (ReservationDTO, time.Time) {
    email := "a@example.org"
    at := time.Date(2026, 10, 17, 19, 0, 0, 0, time.UTC)
    return ReservationDTO{At: at.Format(time.RFC3339), Email: &email, Quantity: 2}, at
}
func TestConversionAndGuardEquivalence(t *testing.T) {
    dto, _ := fixture()
    for _, change := range []func(*ReservationDTO){
        func(d *ReservationDTO){},
        func(d *ReservationDTO){d.At = "bad"},
        func(d *ReservationDTO){d.Email = nil},
        func(d *ReservationDTO){d.Quantity = 0},
        func(d *ReservationDTO){d.Quantity = -1},
    } {
        candidate := dto
        change(&candidate)
        parsed, err := candidate.Parse("id")
        if isValid(candidate) != candidate.isValid() || candidate.isValid() != (err == nil) {
            t.Fatalf("guard mismatch for %+v", candidate)
        }
        if err == nil && (parsed.Quantity != 2 || parsed.Name != "" || parsed.ID != "id") {
            t.Fatalf("unexpected parsed value %+v", parsed)
        }
    }
    parsed, err := dto.Parse("id")
    if err != nil { t.Fatal(err) }
    *dto.Email = "mutated"
    if parsed.Email != "a@example.org" { t.Fatal("parsed email aliased DTO") }
}
func TestExtractedCapacityAndFailures(t *testing.T) {
    dto, _ := fixture()
    sentinel := errors.New("storage failed")
    for _, tc := range []struct{
        name string; rows []Reservation; readErr, writeErr error; outcome Outcome; wantErr bool; calls []string
    }{
        {"accept", []Reservation{{Quantity:8}}, nil,nil,NoContent,false,[]string{"read","write"}},
        {"full", []Reservation{{Quantity:9}}, nil,nil,NoCapacity,false,[]string{"read"}},
        {"large", []Reservation{{Quantity:int(^uint(0)>>1)}},nil,nil,NoCapacity,false,[]string{"read"}},
        {"read failure", nil,sentinel,nil,"",true,[]string{"read"}},
        {"write failure", nil,nil,sentinel,"",true,[]string{"read","write"}},
    } {
        t.Run(tc.name,func(t *testing.T){
            f:=&fakeRepo{rows:tc.rows,readErr:tc.readErr,writeErr:tc.writeErr}
            got,err:=PostExtracted(dto,f)
            if got!=tc.outcome || (err!=nil)!=tc.wantErr || !reflect.DeepEqual(f.calls,tc.calls) {t.Fatalf("got %s %v %v",got,err,f.calls)}
            if tc.wantErr && len(f.saved)!=0 { t.Fatal("saved on failure") }
        })
    }
    dto.Quantity=0
    f:=&fakeRepo{}
    got,err:=PostExtracted(dto,f)
    if got!=BadRequest || err!=nil || len(f.calls)!=0 { t.Fatal("invalid request used I/O") }
}
func TestAllocationBoundariesAndPurity(t *testing.T) {
    _, at:=fixture()
    for _, tc:=range []struct{name string; communal bool; existing []Reservation; quantity int; offset time.Duration; want bool}{
        {"communal remaining",true,[]Reservation{{At:at,Quantity:2}},2,0,true},
        {"private full",false,[]Reservation{{At:at,Quantity:2}},2,0,false},
        {"departure",false,[]Reservation{{At:at.Add(-2*time.Hour),Quantity:4}},4,0,true},
        {"past",true,nil,2,-time.Nanosecond,false},
        {"inconsistent existing",true,[]Reservation{{At:at,Quantity:5}},1,0,false},
        {"conservative",true,[]Reservation{{At:at.Add(-time.Hour),Quantity:2},{At:at.Add(time.Hour),Quantity:2}},2,0,false},
    } {
        t.Run(tc.name,func(t *testing.T){
            tables:=[]Table{{Seats:4,Communal:tc.communal}}
            m,err:=NewMaitreD(tables,2*time.Hour)
            if err!=nil {t.Fatal(err)}
            tables[0].Seats=999
            candidate:=Reservation{At:at.Add(tc.offset),Quantity:tc.quantity}
            original:=append([]Reservation(nil),tc.existing...)
            for i:=0;i<2;i++ {if got:=m.WillAccept(at,tc.existing,candidate);got!=tc.want {t.Fatalf("got %v",got)}}
            if !reflect.DeepEqual(tc.existing,original) {t.Fatal("mutated input")}
        })
    }
    if _,err:=NewMaitreD([]Table{{Seats:0}},time.Hour);err==nil {t.Fatal("invalid seats")}
    if _,err:=NewMaitreD(nil,0);err==nil {t.Fatal("invalid duration")}
    if (MaitreD{}).WillAccept(at,nil,Reservation{At:at,Quantity:1}) {t.Fatal("invalid zero policy")}
}
func TestSequentialFailuresAndEffects(t *testing.T) {
    dto,at:=fixture()
    m,_:=NewMaitreD([]Table{{Seats:2}},time.Hour)
    sentinel:=errors.New("failed")
    for _,tc:=range []struct{name string; supplied string; genErr,readErr,writeErr error; full bool; want Outcome; wantErr bool; calls []string}{
        {"generated","",nil,nil,nil,false,Created,false,[]string{"id","read","now","write"}},
        {"supplied","supplied",nil,nil,nil,false,Created,false,[]string{"read","now","write"}},
        {"ID failure","",sentinel,nil,nil,false,"",true,[]string{"id"}},
        {"read failure","",nil,sentinel,nil,false,"",true,[]string{"id","read"}},
        {"write failure","",nil,nil,sentinel,false,"",true,[]string{"id","read","now","write"}},
        {"no capacity","",nil,nil,nil,true,NoCapacity,false,[]string{"id","read","now"}},
    } {
        t.Run(tc.name,func(t *testing.T){
            candidate:=dto;candidate.ID=tc.supplied
            f:=&fakeRepo{readErr:tc.readErr,writeErr:tc.writeErr}
            if tc.full {f.rows=[]Reservation{{At:at,Quantity:2}}}
            id:=func()(string,error){f.calls=append(f.calls,"id");return "generated",tc.genErr}
            now:=func()time.Time{f.calls=append(f.calls,"now");return at}
            got,err:=PostSequential(candidate,now,id,f,m)
            if got!=tc.want || (err!=nil)!=tc.wantErr || !reflect.DeepEqual(f.calls,tc.calls){t.Fatalf("got %s %v %v",got,err,f.calls)}
            if got==Created {wantID:="generated";if tc.supplied!=""{wantID=tc.supplied};if f.saved[0].ID!=wantID{t.Fatal("wrong id")}}
        })
    }
}

type fakeManager struct { accepted bool; err error; calls int }
func (m *fakeManager) Check(Reservation) (bool,error) { m.calls++; return m.accepted,m.err }
func TestNestedAndSequentialInputFailures(t *testing.T) {
    dto,at:=fixture()
    for _,tc:=range []struct{accepted bool; err error; want Outcome}{
        {true,nil,NoContent},{false,nil,NoCapacity},{false,errors.New("manager failed"),""},
    } {
        manager:=&fakeManager{accepted:tc.accepted,err:tc.err}
        got,err:=PostNested(dto,manager)
        if got!=tc.want||!errors.Is(err,tc.err)||manager.calls!=1{t.Fatal("nested behavior")}
    }
    dto.At="invalid"
    manager:=&fakeManager{}
    if got,err:=PostNested(dto,manager);got!=BadRequest||err!=nil||manager.calls!=0{t.Fatal("nested validation")}
    m,_:=NewMaitreD([]Table{{Seats:2}},time.Hour)
    f:=&fakeRepo{}
    now:=func()time.Time{return at}
    id:=func()(string,error){return "id",nil}
    if got,err:=PostSequential(dto,now,id,f,m);got!=BadRequest||err!=nil||len(f.calls)!=0{t.Fatal("sequential validation")}
    dto,_=fixture()
    emptyID:=func()(string,error){return "",nil}
    if _,err:=PostSequential(dto,now,emptyID,f,m);err==nil||len(f.calls)!=0{t.Fatal("empty generated ID")}
}

package reservations
import (
 "errors"
 "testing"
 "time"
)
func TestBookingBoundaries(t *testing.T) {
 for _, tc := range []struct{name string; quantity int; full bool; wantErr bool}{
  {"exact capacity",10,false,false},{"over capacity",11,false,true},
  {"zero",0,false,true},{"negative",-1,false,true},{"already full",1,true,true},
 } { t.Run(tc.name,func(t *testing.T){
  db:=&FakeReservations{}
  if tc.full { db.entries=[]Reservation{{time.Date(2022,3,18,17,30,0,0,time.UTC),"other","",10}} }
  before:=len(db.entries)
  err:=(ReservationService{db,10}).Book(ReservationDTO{"2022-03-18 17:30","shli@example.org",nil,tc.quantity})
  if (err!=nil)!=tc.wantErr {t.Fatalf("error=%v",err)}
  want:=before; if !tc.wantErr {want++}
  if len(db.entries)!=want {t.Fatalf("writes=%d want=%d",len(db.entries),want)}
 }) }
 for _,dto:=range []ReservationDTO{{"invalid","x",nil,1},{"2022-03-18 17:30"," ",nil,1}} {
  db:=&FakeReservations{}; err:=(ReservationService{db,10}).Book(dto)
  if err==nil||len(db.entries)!=0 {t.Fatal("invalid input stored")}
 }
 db:=&FakeReservations{entries:[]Reservation{{time.Date(2022,3,17,17,30,0,0,time.UTC),"other","",10}}}
 if err:=(ReservationService{db,10}).Book(ReservationDTO{"2022-03-18 17:30","x",nil,10});err!=nil {t.Fatal(err)}
}
type failingRepository struct { failRead bool; writes int }
var errDB=errors.New("database unavailable")
func(f *failingRepository) On(time.Time)([]Reservation,error) {if f.failRead{return nil,errDB};return nil,nil}
func(f *failingRepository) Add(Reservation)error {f.writes++;return errDB}
func TestRepositoryFailures(t *testing.T) {
 for _,read:=range []bool{true,false} {
  db:=&failingRepository{failRead:read}
  err:=(ReservationService{db,10}).Book(ReservationDTO{"2022-03-18 17:30","x",nil,1})
  if !errors.Is(err,errDB) {t.Fatal(err)}
  if read&&db.writes!=0 {t.Fatal("write after failed read")}
 }
}

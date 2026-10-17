package httpreservations
import (
 "net/http"
 "net/http/httptest"
 "strings"
 "testing"
 "time"
)
func TestInvalidJSONAndDomain(t *testing.T) {
 for _,body:=range []string{
  `{`, `null`, `{}`, `{"date":"2022-03-18 17:30","email":"x","quantity":0}`,
  `{"date":"2022-03-18 17:30","email":"x","quantity":-1}`,
  `{"date":"2022-03-18 17:30","email":"x","quantity":1.5}`,
  `{"date":"2022-03-18 17:30","email":"x","quantity":null}`,
  `{"date":"invalid","email":"x","quantity":1}`,
  `{"date":"2022-03-18 17:30","email":" ","quantity":1}`,
  `{"date":"2022-03-18 17:30","email":"x","quantity":1,"name":1}`,
  `{"date":"2022-03-18 17:30","email":"x","quantity":1} {}`,
 } { t.Run(body,func(t *testing.T){
  db:=&FakeReservations{}; recorder:=httptest.NewRecorder()
  reservationsHandler(db).ServeHTTP(recorder,httptest.NewRequest(http.MethodPost,"/reservations",strings.NewReader(body)))
  if recorder.Code!=400||len(db.Entries)!=0 {t.Fatalf("status=%d stored=%#v",recorder.Code,db.Entries)}
 }) }
}
func TestHTTPStoredOutcomeAndCapacity(t *testing.T) {
 for _,quantity:=range []int{1,10,11} {
  db:=&FakeReservations{}
  response:=postReservation(t,db,ReservationDTO{"2022-03-18 17:30","shli@example.org",nil,quantity})
  if quantity>10 {if response.StatusCode!=409||len(db.Entries)!=0{t.Fatal("capacity failure")};continue}
  expected:=Reservation{time.Date(2022,3,18,17,30,0,0,time.UTC),"shli@example.org","",quantity}
  if response.StatusCode!=201||len(db.Entries)!=1||db.Entries[0]!=expected{t.Fatalf("stored=%#v",db.Entries)}
 }
}

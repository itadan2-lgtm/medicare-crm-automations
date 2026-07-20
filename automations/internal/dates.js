// Pure date helpers, no Notion or network dependency, so they're easy to
// unit test on their own.

const MS_PER_HOUR = 3600 * 1000;
const MS_PER_DAY = 24 * MS_PER_HOUR;

function hoursBetween(a, b) {
  return (new Date(b) - new Date(a)) / MS_PER_HOUR;
}

function daysBetween(a, b) {
  return Math.floor((new Date(b) - new Date(a)) / MS_PER_DAY);
}

function monthsBetween(a, b) {
  const d1 = new Date(a), d2 = new Date(b);
  let months = (d2.getFullYear() - d1.getFullYear()) * 12 + (d2.getMonth() - d1.getMonth());
  if (d2.getDate() < d1.getDate()) months -= 1;
  return months;
}

// Date of someone's Nth birthday, given their DOB.
function nthBirthday(dobIso, n) {
  const dob = new Date(dobIso);
  return new Date(Date.UTC(dob.getUTCFullYear() + n, dob.getUTCMonth(), dob.getUTCDate()));
}

// True if date falls within [start, end], comparing by UTC day.
function isWithin(date, start, end) {
  const d = new Date(date).setUTCHours(0, 0, 0, 0);
  return d >= new Date(start).setUTCHours(0, 0, 0, 0) && d <= new Date(end).setUTCHours(23, 59, 59, 999);
}

function addMonths(date, n) {
  const d = new Date(date);
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + n, d.getUTCDate()));
}

module.exports = { hoursBetween, daysBetween, monthsBetween, nthBirthday, isWithin, addMonths, MS_PER_DAY };

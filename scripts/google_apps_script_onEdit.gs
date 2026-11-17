/**
 * Google Apps Script for "Liqour Stock Data"
 * 
 * Automates Truck Lifecycle Tracking on "Truck Endorsements" and "Country Spirit Endorsements":
 * 1. Changing Status to "Not Opened" or "Unloading" -> auto-fills DateArrived with today's date (if blank) & colors row.
 * 2. Changing Status to "Completed" -> auto-fills DateCompleted (and DateArrived if blank) & colors row.
 * 3. Changing Status to "Not Arrived" -> colors row grey.
 * 4. Auto-sorts range (Status Z-A, DateArrived Z-A, DateofEndorsement Z-A) so active trucks stay on top!
 * 
 * Instructions:
 * 1. Open "Liqour Stock Data" in Google Sheets.
 * 2. Click "Extensions" -> "Apps Script".
 * 3. Paste this entire code into Code.gs, replacing any existing code.
 * 4. Click "Save" (Floppy disk icon). Done! It will trigger automatically whenever you edit Status.
 */

function onEdit(e) {
  if (!e || !e.range) return;
  
  var sheet = e.range.getSheet();
  var sheetName = sheet.getName();
  
  // Only operate on endorsement sheets
  if (sheetName !== "Truck Endorsements" && sheetName !== "Country Spirit Endorsements") {
    return;
  }
  
  var row = e.range.getRow();
  var col = e.range.getColumn();
  
  // Column 6 is Status (A=1, B=2, C=3, D=4, E=5, F=6)
  if (row <= 1 || col !== 6) {
    return;
  }
  
  var newStatus = String(e.value || sheet.getRange(row, 6).getValue()).trim();
  if (!newStatus) return;
  
  var now = new Date();
  var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var day = now.getDate();
  var month = months[now.getMonth()];
  var year = now.getFullYear();
  var formattedToday = day + "-" + month + "-" + year; // e.g., 14-Nov-2026
  
  var dateArrivedCell = sheet.getRange(row, 7);    // Column G: DateArrived
  var dateCompletedCell = sheet.getRange(row, 8);  // Column H: DateCompleted
  var wholeRowRange = sheet.getRange(row, 1, 1, 9);
  
  var statusLower = newStatus.toLowerCase();
  
  if (statusLower === "not opened" || statusLower === "unloading") {
    // Fill DateArrived if empty
    var currentArrived = String(dateArrivedCell.getValue() || "").trim();
    if (!currentArrived) {
      dateArrivedCell.setValue(formattedToday);
    }
    
    // Apply Row Colors
    if (statusLower === "unloading") {
      wholeRowRange.setBackground("#FFF2CC"); // Soft Yellow
    } else {
      wholeRowRange.setBackground("#F4CCCC"); // Soft Red
    }
  } else if (statusLower === "completed") {
    // Fill DateCompleted and DateArrived if empty
    dateCompletedCell.setValue(formattedToday);
    var currentArrived = String(dateArrivedCell.getValue() || "").trim();
    if (!currentArrived) {
      dateArrivedCell.setValue(formattedToday);
    }
    wholeRowRange.setBackground("#D9EAD3"); // Soft Green
  } else if (statusLower === "not arrived") {
    wholeRowRange.setBackground("#D9D9D9"); // Soft Grey
  }
  
  // Auto-Sort the Sheet after editing status
  autoSortEndorsementsSheet(sheet);
}

function autoSortEndorsementsSheet(sheet) {
  var lastRow = sheet.getLastRow();
  if (lastRow <= 2) return;
  
  // Sort Range A2:I<lastRow>
  var sortRange = sheet.getRange(2, 1, lastRow - 1, 9);
  sortRange.sort([
    { column: 6, ascending: false }, // Status Z-A: Unloading -> Not Opened -> Not Arrived -> Completed
    { column: 7, ascending: false }, // DateArrived Z-A: Newest arrivals first, incident notes on top
    { column: 1, ascending: false }  // DateofEndorsement Z-A: Newest endorsed trucks first
  ]);
}

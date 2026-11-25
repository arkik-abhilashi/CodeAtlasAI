On Error Resume Next
Set w = CreateObject("Word.Application")
If Err.Number <> 0 Then WScript.Echo "NOAPP " & Err.Description: WScript.Quit 2
w.Visible = False
w.DisplayAlerts = 0
w.Options.UpdateLinksAtOpen = False
path = "C:\Users\arkik\OneDrive\Desktop\Major\output\CodeAtlas_AI_Major_Project_Report_Updated.docx"
Set d = w.Documents.Open(path, False, True, False)
If Err.Number <> 0 Then WScript.Echo "OPENFAIL " & Err.Description: w.Quit: WScript.Quit 3
WScript.Echo "PAGES=" & d.ComputeStatistics(2)
For Each p In d.Paragraphs
 t = Trim(Replace(Replace(p.Range.Text, Chr(13), ""), Chr(7), ""))
 If Left(t, 9) = "Chapter 4" Or Left(t, 9) = "Chapter 5" Or Left(t, 10) = "Appendix C" Or Left(t, 10) = "Appendix D" Or Left(t, 6) = "Table " Or Left(t, 7) = "4.1.1 " Or Left(t, 7) = "4.2.1 " Or Left(t, 7) = "5.1.3 " Or Left(t, 7) = "5.1.4 " Or Left(t, 7) = "5.1.5 " Or Left(t, 7) = "5.1.6 " Then
  WScript.Echo CStr(p.Range.Information(3)) & "|" & CStr(p.Range.Information(1)) & "|" & t
End If
Next
pdf = "C:\Users\arkik\OneDrive\Desktop\Major\output\report_render\updated_word_render.pdf"
d.ExportAsFixedFormat pdf, 17, False
d.Close False
w.Quit



On Error Resume Next
Set w = CreateObject("Word.Application")
w.Visible = False
w.DisplayAlerts = 0
w.Options.UpdateLinksAtOpen = False
path = "C:\Users\arkik\OneDrive\Desktop\Major\output\CodeAtlas_AI_Major_Project_Report_Updated.docx"
Set d = w.Documents.Open(path, False, True, False)
Set fs = CreateObject("Scripting.FileSystemObject")
Set f = fs.CreateTextFile("C:\Users\arkik\OneDrive\Desktop\Major\output\report_render\page_map.txt", True, True)
f.WriteLine "PAGES|" & d.ComputeStatistics(2)
For Each p In d.Paragraphs
 t = Trim(Replace(Replace(p.Range.Text, Chr(13), ""), Chr(7), ""))
 sty = p.Range.Style.NameLocal
 If Left(sty, 7) = "Heading" Or Left(t, 6) = "Table " Or Left(t, 7) = "Figure " Then
  If t <> "" Then f.WriteLine CStr(p.Range.Information(3)) & "|" & CStr(p.Range.Information(1)) & "|" & sty & "|" & t
 End If
Next
f.Close
d.Close False
w.Quit


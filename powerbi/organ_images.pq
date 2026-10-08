// Power Query (M) for the `organ_images` table.
// Reads the small PNGs in assets/organs/powerbi, converts each to base64 text and
// splits it into 20,000-character chunks (Power BI text cells are capped at ~32k chars).
// The `Organ Image` measure stitches the chunks back together.
//
// >>> Change the folder path below to where the project lives on YOUR computer. <<<
let
    Source = Folder.Files("C:\Users\Kwenev Steve\Documents\Web\Advanced Dashboards\cardiovascular-risk-explorer\assets\organs\powerbi"),
    Png = Table.SelectRows(Source, each Text.Lower([Extension]) = ".png"),
    AddB64 = Table.AddColumn(Png, "B64", each Binary.ToText([Content], BinaryEncoding.Base64), type text),
    AddChunks = Table.AddColumn(AddB64, "Chunks", each
        let t = [B64], n = Number.RoundUp(Text.Length(t) / 20000)
        in List.Transform({0 .. n - 1}, (i) => [Idx = i, Part = Text.Middle(t, i * 20000, 20000)])),
    Keep = Table.SelectColumns(AddChunks, {"Name", "Chunks"}),
    Expand = Table.ExpandListColumn(Keep, "Chunks"),
    Rec = Table.ExpandRecordColumn(Expand, "Chunks", {"Idx", "Part"}),
    AddKey = Table.AddColumn(Rec, "Image", each Text.BeforeDelimiter([Name], "."), type text),
    Final = Table.TransformColumnTypes(Table.SelectColumns(AddKey, {"Image", "Idx", "Part"}), {{"Idx", Int64.Type}, {"Part", type text}})
in
    Final

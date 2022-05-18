PARAMETER_TAGS = {
    "manufacturer": [0x08, 0x70],
    "organ": [0x18, 0x15],
    "TE": [0x18, 0x81],
    "TR": [0x18, 0x80],
    "B0": [0x18, 0x87],
    "FlipAngle": [0x18, 0x1314],
    "BWPx": [0x18, 0x95],
    "ETL": [0x18, 0x91],
    "Comments": [0x20, 0x4000],
    "ScanningSequence": [0x18, 0x20],
    "SequenceVariant": [0x18, 0x21],
    "MRAcquisitionType": [0x18, 0x23],
    "PhaseEncodingLines": [0x18, 0x89],
    "BandwidthPerPixelPhaseEncode": [0x19, 0x1028],
    "EchoTrainLength": [0x18, 0x91],
    "BandwidthPerPixel": [0x18, 0x95],
    "PedDCM": [0x18, 0x1312],
}
HEADER_TAGS = {
    "ImageHeaderInfo": [0x29, 0x1010],
    "SeriesHeaderInfo": [0x29, 0x1020]
}
SODict = {
    "1": "SEQUENTIAL",
    "2": "INTERLEAVED",
    "4": "SINGLESHOT"
}
SSDict = {
    "SE": "Spin Echo",
    "IR": "Inversion Recovery",
    "GR": "Gradient Recalled",
    "EP": "Echo Planar",
    "RM": "Research Mode"
}
SVDict = {
    "SK": "segmented k-space",
    "MTC": "magnetization transfer contrast",
    "SS": "steady state",
    "TRSS": "time reversed steady state",
    "SP": "spoiled",
    "MP": "MAG prepared",
    "OSP": "oversampling phase",
    "NONE": "no sequence variant"
}
ATDict = ["2D", "3D"]


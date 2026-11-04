"""Where each curve is in the datasheet PDFs (page coordinates in PDF points, read from the pages'
vector graphics and tick labels, see pdfpaths.py)."""

SPECS = {
    # ---------------------------------------------------------------- Portra 400 (E-4050), page 4
    "portra400_char": {
        "pdf": "portra400.pdf", "page": 3, "rect": (81.2, 102.9, 265.6, 287.4),
        "drawings": [34, 35, 36],
        "xcal": ((81.2, -4.0), (265.6, 1.0)), "ycal": ((287.4, 0.0), (102.9, 4.0)),
    },
    "portra400_sens": {
        "pdf": "portra400.pdf", "page": 3, "rect": (76.2, 343.1, 276.7, 494.6),
        "drawings": [52, 53, 54],
        "xcal": ((76.2, 250.0), (276.7, 750.0)), "ycal": ((494.6, 0.0), (343.1, 4.0)),
    },
    "portra400_dye": {
        "pdf": "portra400.pdf", "page": 3, "rect": (357.1, 103.7, 541.8, 288.1),
        "drawings": [68, 69],
        "xcal": ((357.1, 400.0), (541.8, 700.0)), "ycal": ((288.1, 0.0), (103.7, 2.5)),
    },
    # ---------------------------------------------------------------- Gold 200 (E-7022), page 4
    "gold200_char": {
        "pdf": "gold200.pdf", "page": 3, "rect": (81.7, 71.9, 266.2, 256.4),
        "drawings": [36, 37, 38],
        "xcal": ((81.7, -3.0), (266.2, 1.0)), "ycal": ((256.4, 0.0), (71.9, 4.0)),
    },
    "gold200_sens": {
        "pdf": "gold200.pdf", "page": 3, "rect": (74.9, 317.9, 275.4, 469.4),
        "drawings": list(range(68, 133)),
        "xcal": ((74.9, 250.0), (275.4, 750.0)), "ycal": ((469.4, 0.0), (317.9, 4.0)),
    },
    "gold200_dye": {
        "pdf": "gold200.pdf", "page": 3, "rect": (357.1, 55.4, 541.4, 239.7),
        "drawings": [138, 139],
        "xcal": ((357.1, 400.0), (541.4, 700.0)), "ycal": ((239.7, 0.0), (55.4, 2.5)),
    },
}

STOP = 0.30103  # log10(2)

SPECS.update({
    # ---------------------------------------------------------------- VISION3 500T (H-1-5219), pages 4-5
    # sensitometry plotted over camera stops (tungsten exposure, ECN-2 densitometry)
    "vision500t_char": {
        "pdf": "vision3_500t.pdf", "page": 3, "rect": (353.6, 122.3, 538.2, 306.8),
        "drawings": [93, 94, 95],
        "xcal": ((365.1, -7 * STOP), (526.7, 7 * STOP)), "ycal": ((306.8, 0.0), (122.3, 3.0)),
    },
    "vision500t_sens": {
        "pdf": "vision3_500t.pdf", "page": 3, "rect": (352.7, 518.3, 553.1, 669.8),
        "drawings": [110, 111, 112],
        "xcal": ((352.7, 250.0), (553.1, 750.0)), "ycal": ((669.8, 0.0), (518.3, 4.0)),
    },
    # yellow, magenta, cyan (peak-normalized), midscale neutral, minimum density (dashed)
    "vision500t_dye": {
        "pdf": "vision3_500t.pdf", "page": 4, "rect": (81.6, 155.0, 265.9, 340.0),
        "drawings": [28, 29, 30, 31, 32],
        "xcal": ((81.6, 400.0), (265.9, 800.0)), "ycal": ((321.5, 0.0), (173.9, 1.6)),
        "join": False,
    },
})

SPECS.update({
    # ---------------------------------------------------------------- VISION Color Print Film 2383 (H-1-2383t), pages 5-6
    "print2383_char": {
        "pdf": "print2383_ti.pdf", "page": 4, "rect": (96.5, 82.6, 280.9, 267.1),
        "drawings": [16, 17, 18],
        "xcal": ((96.5, -3.0), (280.9, 3.0)), "ycal": ((267.1, 0.0), (82.6, 6.0)),
    },
    "print2383_sens": {
        "pdf": "print2383_ti.pdf", "page": 5, "rect": (74.4, 56.4, 274.9, 207.9),
        "drawings": [16, 17, 18, 19, 20], "join": False,
        "xcal": ((74.4, 250.0), (274.9, 750.0)), "ycal": ((94.5, 0.0), (170.2, -2.0)),
    },
    "print2383_dye": {
        "pdf": "print2383_ti.pdf", "page": 5, "rect": (357.7, 55.9, 541.9, 240.2),
        "drawings": [44, 45, 46, 47], "join": False,
        "xcal": ((357.7, 250.0), (541.9, 750.0)), "ycal": ((240.3, 0.0), (108.7, 1.0)),
    },
})

SPECS.update({
    # ---------------------------------------------------------------- Ektar 100 (E-4046), page 4
    "ektar100_char": {
        "pdf": "ektar100.pdf", "page": 3, "rect": (81.2, 107.9, 265.7, 292.4), "drawings": [31, 32, 33],
        "xcal": ((81.2, -3.0), (265.7, 2.0)), "ycal": ((292.4, 0.0), (107.9, 4.0)),
    },
    "ektar100_sens": {
        "pdf": "ektar100.pdf", "page": 3, "rect": (74.2, 356.6, 274.7, 508.0), "drawings": [48, 49, 50],
        "xcal": ((74.2, 250.0), (274.7, 750.0)), "ycal": ((508.0, 0.0), (356.6, 3.0)),
    },
    "ektar100_dye": {
        "pdf": "ektar100.pdf", "page": 3, "rect": (357.5, 106.0, 541.8, 290.4), "drawings": [67, 68],
        "xcal": ((357.5, 400.0), (541.8, 700.0)), "ycal": ((290.4, 0.0), (106.0, 2.5)),
    },
    # ---------------------------------------------------------------- Portra 800 (E-4040), pages 4-5, EI 800 curves
    "portra800_char": {
        "pdf": "portra800.pdf", "page": 3, "rect": (81.6, 74.5, 266.2, 258.9), "drawings": [10, 11, 12],
        "xcal": ((81.6, -4.0), (266.2, 1.0)), "ycal": ((258.9, 0.0), (74.5, 4.0)),
    },
    "portra800_char_push1": {  # EI 1600, 1 stop push
        "pdf": "portra800.pdf", "page": 3, "rect": (81.1, 314.1, 265.6, 498.5), "drawings": [25, 26, 27],
        "xcal": ((81.1, -4.0), (265.6, 1.0)), "ycal": ((498.5, 0.0), (314.1, 4.0)),
    },
    "portra800_char_push2": {  # EI 3200, 2 stop push
        "pdf": "portra800.pdf", "page": 3, "rect": (357.6, 71.0, 542.2, 255.5), "drawings": [43, 44, 45],
        "xcal": ((357.6, -4.0), (542.2, 1.0)), "ycal": ((255.5, 0.0), (71.0, 4.0)),
    },
    "portra800_sens": {
        "pdf": "portra800.pdf", "page": 3, "rect": (350.2, 313.7, 550.9, 465.4), "drawings": [63, 64, 65],
        "xcal": ((350.2, 250.0), (550.9, 750.0)), "ycal": ((465.4, 0.0), (313.7, 4.0)),
    },
    "portra800_dye": {
        "pdf": "portra800.pdf", "page": 4, "rect": (81.1, 101.8, 265.4, 286.1), "drawings": [33, 34],
        "xcal": ((81.1, 400.0), (265.4, 700.0)), "ycal": ((286.1, 0.0), (101.8, 2.5)),
    },
    # ---------------------------------------------------------------- UltraMax 400 (E-7023), page 4
    "ultramax400_char": {
        "pdf": "ultramax400.pdf", "page": 3, "rect": (81.1, 112.7, 265.9, 297.4), "drawings": [33, 34, 35],
        "xcal": ((81.1, -4.0), (265.9, 1.0)), "ycal": ((297.4, 0.0), (112.7, 4.0)),
    },
    "ultramax400_sens": {
        "pdf": "ultramax400.pdf", "page": 3, "rect": (76.6, 371.0, 277.6, 522.6), "drawings": [50, 51, 52],
        "xcal": ((76.6, 250.0), (277.6, 750.0)), "ycal": ((522.6, 0.0), (371.0, 4.0)),
    },
    "ultramax400_dye": {
        "pdf": "ultramax400.pdf", "page": 3, "rect": (357.2, 113.0, 541.5, 297.2), "drawings": [65, 66],
        "xcal": ((357.2, 400.0), (541.5, 700.0)), "ycal": ((297.2, 0.0), (113.0, 2.5)),
    },
    # ---------------------------------------------------------------- VISION3 250D (H-1-5207t), pages 3-4
    "vision250d_char": {
        "pdf": "vision250d_old.pdf", "page": 2, "rect": (369.1, 90.2, 553.6, 274.7), "drawings": [30, 31, 32],
        "xcal": ((369.1, -8 * STOP), (553.6, 8 * STOP)), "ycal": ((274.7, 0.0), (90.2, 3.0)),
    },
    "vision250d_sens": {
        "pdf": "vision250d_old.pdf", "page": 3, "rect": (352.7, 57.0, 553.2, 208.7), "drawings": [108, 109, 110],
        "xcal": ((352.7, 250.0), (553.2, 750.0)), "ycal": ((208.5, 0.0), (57.0, 4.0)),
    },
    # yellow, magenta, cyan (peak-normalized)
    "vision250d_dye": {
        "pdf": "vision250d_old.pdf", "page": 3, "rect": (354.3, 342.3, 538.7, 526.6), "drawings": [128, 129, 130],
        "xcal": ((354.3, 400.0), (538.7, 800.0)), "ycal": ((508.1, 0.0), (360.8, 1.6)), "join": False,
    },
    "vision250d_dmin": {
        "pdf": "vision250d_old.pdf", "page": 3, "rect": (354.3, 342.3, 538.7, 526.6), "drawings": [132],
        "xcal": ((354.3, 400.0), (538.7, 800.0)), "ycal": ((508.1, 0.0), (360.8, 1.6)),
    },
    # ---------------------------------------------------------------- TRI-X 400 (F-4017), page 8
    # one panchromatic layer; spectral sensitivity for D = 0.3 and 1.0 above gross fog
    "trix400_sens": {
        "pdf": "trix400.pdf", "page": 7, "rect": (74.9, 291.7, 275.4, 443.0), "drawings": [73, 74],
        "xcal": ((74.9, 250.0), (275.4, 750.0)), "ycal": ((443.0, 0.0), (291.7, 4.0)),
    },
    # 35 mm, T-MAX Developer small tank 20 C; 7 minutes (short dashes)
    "trix400_char": {  # 7 minutes (normal); the same plot holds 6, 9 and 11 minutes
        "pdf": "trix400.pdf", "page": 7, "rect": (354.4, 63.5, 538.9, 248.0), "drawings": [101],
        "xcal": ((354.4, -4.0), (538.9, 1.0)), "ycal": ((248.0, 0.0), (63.5, 4.0)),
    },
    "trix400_char_6": {
        "pdf": "trix400.pdf", "page": 7, "rect": (354.4, 63.5, 538.9, 248.0), "drawings": [102],
        "xcal": ((354.4, -4.0), (538.9, 1.0)), "ycal": ((248.0, 0.0), (63.5, 4.0)),
    },
    "trix400_char_9": {
        "pdf": "trix400.pdf", "page": 7, "rect": (354.4, 63.5, 538.9, 248.0), "drawings": [103],
        "xcal": ((354.4, -4.0), (538.9, 1.0)), "ycal": ((248.0, 0.0), (63.5, 4.0)),
    },
    "trix400_char_11": {
        "pdf": "trix400.pdf", "page": 7, "rect": (354.4, 63.5, 538.9, 248.0), "drawings": [104],
        "xcal": ((354.4, -4.0), (538.9, 1.0)), "ycal": ((248.0, 0.0), (63.5, 4.0)),
    },
    # ---------------------------------------------------------------- T-MAX 100 (F-4016), pages 14-15
    "tmax100_sens": {
        "pdf": "tmax.pdf", "page": 13, "rect": (74.7, 360.0, 275.2, 511.5), "drawings": [22, 23],
        "xcal": ((74.7, 250.0), (275.2, 750.0)), "ycal": ((511.5, -2.0), (360.0, 2.0)),
    },
    # D-76 small tank 20 C; 7.5 minutes (short dashes)
    "tmax100_char": {  # D-76, 7.5 minutes (normal); the same plot holds 6 and 10 minutes
        "pdf": "tmax.pdf", "page": 14, "rect": (93.8, 84.9, 278.2, 269.4), "drawings": [8],
        "xcal": ((93.8, -4.0), (278.2, 1.0)), "ycal": ((269.4, 0.0), (84.9, 4.0)),
    },
    "tmax100_char_6": {
        "pdf": "tmax.pdf", "page": 14, "rect": (93.8, 84.9, 278.2, 269.4), "drawings": [10],
        "xcal": ((93.8, -4.0), (278.2, 1.0)), "ycal": ((269.4, 0.0), (84.9, 4.0)),
    },
    "tmax100_char_10": {
        "pdf": "tmax.pdf", "page": 14, "rect": (93.8, 84.9, 278.2, 269.4), "drawings": [9],
        "xcal": ((93.8, -4.0), (278.2, 1.0)), "ycal": ((269.4, 0.0), (84.9, 4.0)),
    },
})

# ---------------------------------------------------------------- the v0.8 films
# Where a datasheet draws all curves of a plot as one path (Kodak VISION3 50D, the Fujifilm sheets),
# digitize.py splits it at the pen-ups. Fujifilm plots have no axis text (glyphs are outlines), so
# the calibration points are the plot's grid lines, read with pdfpaths.py.
SPECS.update({
    # ---------------------------------------------------------------- Portra 160 (E-4051), page 4
    "portra160_char": {
        "pdf": "portra160.pdf", "page": 3, "rect": (81.4, 102.1, 266.0, 286.6), "drawings": [31, 32, 33],
        "xcal": ((81.4, -4.0), (266.0, 1.0)), "ycal": ((286.6, 0.0), (102.1, 4.0)),
    },
    "portra160_sens": {
        "pdf": "portra160.pdf", "page": 3, "rect": (73.8, 348.0, 274.2, 499.6), "drawings": [49, 50, 51],
        "xcal": ((73.8, 250.0), (274.2, 750.0)), "ycal": ((499.6, -1.0), (348.0, 3.0)),
    },
    "portra160_dye": {
        "pdf": "portra160.pdf", "page": 3, "rect": (355.1, 101.2, 539.5, 285.5), "drawings": [65, 66],
        "xcal": ((355.1, 400.0), (539.5, 700.0)), "ycal": ((285.5, 0.0), (101.2, 2.5)),
    },
    # ---------------------------------------------------------------- VISION3 200T (H-1-5213t, Spanish edition), pages 4-5
    "vision200t_char": {  # x in camera stops, -8 .. 8
        "pdf": "vision200t.pdf", "page": 3, "rect": (357.5, 132.4, 542.1, 316.9), "drawings": [62, 63, 64],
        "xcal": ((357.5, -8 * STOP), (542.1, 8 * STOP)), "ycal": ((316.9, 0.0), (132.4, 3.0)),
    },
    "vision200t_sens": {
        "pdf": "vision200t.pdf", "page": 3, "rect": (350.7, 536.8, 551.2, 688.2), "drawings": [100, 101, 102],
        "xcal": ((350.7, 250.0), (551.2, 750.0)), "ycal": ((688.2, 0.0), (536.8, 4.0)),
    },
    "vision200t_dye": {  # the three dyes (the neutral and the dashed D-min are separate drawings)
        "pdf": "vision200t.pdf", "page": 4, "rect": (89.9, 123.9, 274.2, 308.3), "drawings": [22, 23, 24],
        "xcal": ((89.9, 400.0), (274.2, 800.0)), "ycal": ((308.3, -0.2), (123.9, 1.8)), "join": False,
    },
    "vision200t_dmin": {
        "pdf": "vision200t.pdf", "page": 4, "rect": (89.9, 123.9, 274.2, 308.3), "drawings": [21],
        "xcal": ((89.9, 400.0), (274.2, 800.0)), "ycal": ((308.3, -0.2), (123.9, 1.8)),
    },
    # ---------------------------------------------------------------- VISION3 50D (TI-2657, Spanish edition), pages 4-5
    "vision50d_char": {  # all three curves in one path
        "pdf": "vision50d.pdf", "page": 3, "rect": (392.1, 170.3, 576.6, 354.8), "drawings": [33, 34],
        "xcal": ((392.1, -8 * STOP), (576.6, 8 * STOP)), "ycal": ((354.8, 0.0), (170.3, 3.0)), "join": False,
    },
    "vision50d_sens": {
        "pdf": "vision50d.pdf", "page": 3, "rect": (388.7, 568.5, 589.2, 719.9), "drawings": [38],
        "xcal": ((388.7, 250.0), (589.2, 750.0)), "ycal": ((719.9, 0.0), (568.5, 4.0)), "join": False,
    },
    "vision50d_dye": {
        "pdf": "vision50d.pdf", "page": 4, "rect": (129.4, 160.9, 313.8, 345.2), "drawings": [4],
        "xcal": ((129.4, 400.0), (313.8, 800.0)), "ycal": ((345.2, -0.2), (160.9, 1.8)), "join": False,
    },
    "vision50d_dmin": {
        "pdf": "vision50d.pdf", "page": 4, "rect": (129.4, 160.9, 313.8, 345.2), "drawings": [5],
        "xcal": ((129.4, 400.0), (313.8, 800.0)), "ycal": ((345.2, -0.2), (160.9, 1.8)),
    },
    # ---------------------------------------------------------------- Ektachrome E100 (E-4000), pages 3-4 (reversal)
    "ektachrome100_char": {
        "pdf": "ektachrome100.pdf", "page": 2, "rect": (368.7, 358.6, 554.0, 543.0), "drawings": [64, 65, 66],
        "xcal": ((368.7, -3.0), (554.0, 1.0)), "ycal": ((543.0, 0.0), (358.6, 4.0)), "join": False,
    },
    "ektachrome100_sens": {
        "pdf": "ektachrome100.pdf", "page": 3, "rect": (74.3, 107.0, 274.9, 258.5), "drawings": [39, 40, 41],
        "xcal": ((74.3, 250.0), (274.9, 750.0)), "ycal": ((258.5, -2.0), (107.0, 2.0)),
    },
    "ektachrome100_dye": {  # the three dyes (D78 is their sum, the visual neutral)
        "pdf": "ektachrome100.pdf", "page": 3, "rect": (70.6, 349.6, 271.1, 501.1), "drawings": [73, 76, 77],
        "xcal": ((70.6, 400.0), (271.1, 700.0)), "ycal": ((501.1, 0.0), (349.6, 1.4)),
    },
    # ---------------------------------------------------------------- Fujicolor Pro 400H (AF3-176E), page 8
    "pro400h_char": {  # three curves in one path; calibration from the grid lines
        "pdf": "pro400h.pdf", "page": 7, "rect": (78.6, 105.0, 285.5, 249.6), "drawings": [66],
        "xcal": ((99.0, -3.5), (264.8, 0.5)), "ycal": ((228.7, 0.5), (125.4, 3.0)), "join": False,
    },
    "pro400h_sens": {  # relative log sensitivity: the grid's two horizontal lines are 1.0 apart
        "pdf": "pro400h.pdf", "page": 7, "rect": (336.7, 104.7, 515.7, 258.1), "drawings": [365],
        "xcal": ((346.9, 400.0), (504.5, 700.0)), "ycal": ((207.0, 0.0), (155.8, 1.0)), "join": False,
    },
    "pro400h_dye": {  # mid-scale neutral and D-min in one path
        "pdf": "pro400h.pdf", "page": 7, "rect": (334.7, 374.4, 533.9, 538.7), "drawings": [624],
        "xcal": ((334.9, 400.0), (522.7, 700.0)), "ycal": ((502.2, 0.5), (386.0, 2.0)), "join": False,
    },
    # ---------------------------------------------------------------- Fujicolor Superia X-TRA 400 (AF3-0217E), page 6
    "superia400_char": {
        "pdf": "superia400.pdf", "page": 5, "rect": (85.1, 104.5, 280.8, 277.5), "drawings": [40],
        "xcal": ((106.6, -3.5), (258.9, 0.0)), "ycal": ((256.3, 0.5), (125.6, 3.5)), "join": False,
    },
    "superia400_sens": {
        "pdf": "superia400.pdf", "page": 5, "rect": (339.1, 104.8, 533.6, 275.6), "drawings": [48],
        "xcal": ((350.4, 400.0), (521.9, 700.0)), "ycal": ((219.1, 0.0), (161.9, 1.0)), "join": False,
    },
    "superia400_dye": {
        "pdf": "superia400.pdf", "page": 5, "rect": (333.5, 388.4, 538.7, 536.8), "drawings": [60],
        "xcal": ((344.9, 400.0), (527.3, 700.0)), "ycal": ((507.1, 0.5), (418.3, 2.0)), "join": False,
    },
    # ---------------------------------------------------------------- Fujichrome Velvia 100 (AF3-202E), page 8 (reversal)
    "velvia100_char": {  # R solid, G dash-dot, B dashed
        "pdf": "velvia100.pdf", "page": 7, "rect": (86.0, 174.2, 281.9, 347.5), "drawings": [142, 143, 144],
        "xcal": ((107.6, -3.0), (281.8, 1.0)), "ycal": ((326.3, 0.5), (195.7, 3.5)), "join": False,
    },
    "velvia100_sens": {
        "pdf": "velvia100.pdf", "page": 7, "rect": (335.5, 174.9, 533.8, 345.1), "drawings": [292],
        "xcal": ((347.0, 400.0), (521.8, 700.0)), "ycal": ((262.8, 0.0), (205.1, 1.0)), "join": False,
    },
    "velvia100_dye": {
        "pdf": "velvia100.pdf", "page": 7, "rect": (333.2, 449.4, 534.4, 596.8), "drawings": [22],
        "xcal": ((345.0, 400.0), (522.2, 700.0)), "ycal": ((537.3, 0.5), (477.7, 1.0)), "join": False,
    },
    # ---------------------------------------------------------------- Ilford FP4 Plus (fact sheet April 2004), pages 1 and 4
    "fp4plus_sens": {  # wedge spectrogram to tungsten light (2850 K), relative log sensitivity
        "pdf": "fp4plus_2004.pdf", "page": 0, "rect": (327.6, 408.8, 510.9, 488.0), "drawings": [44],
        "xcal": ((354.3, 400.0), (484.2, 650.0)), "ycal": ((455.2, 0.5), (428.9, 1.0)),
    },
    "fp4plus_char": {  # ILFOTEC HC 1+31, 8 min; x is RELATIVE log exposure (anchored in film_data.py)
        "pdf": "fp4plus_2004.pdf", "page": 3, "rect": (328.0, 562.6, 513.2, 684.9), "drawings": [172],
        "xcal": ((369.2, 1.0), (492.6, 4.0)), "ycal": ((644.2, 1.0), (603.9, 2.0)),
    },
    # ---------------------------------------------------------------- T-MAX 400 (F-4016), pages 14 and 17
    "tmax400_sens": {  # the two density levels, as for T-MAX 100
        "pdf": "tmax.pdf", "page": 13, "rect": (350.7, 368.8, 551.2, 520.3), "drawings": [37, 38],
        "xcal": ((350.7, 250.0), (551.2, 750.0)), "ycal": ((520.3, -2.0), (368.8, 2.0)),
    },
    "tmax400_char": {  # D-76, small tank, 20 C: 6, 8, 10 and 12 min, all four in one path
        "pdf": "tmax.pdf", "page": 16, "rect": (86.7, 82.4, 271.2, 266.9), "drawings": [13],
        "xcal": ((86.7, -4.0), (271.2, 0.0)), "ycal": ((266.9, 0.0), (82.4, 4.0)), "join": False,
    },
    # ---------------------------------------------------------------- T-MAX P3200 (F-4016), pages 25 and 26
    "tmaxp3200_sens": {
        "pdf": "tmax.pdf", "page": 24, "rect": (362.7, 355.8, 563.2, 507.3), "drawings": [28],
        "xcal": ((362.7, 250.0), (563.2, 750.0)), "ycal": ((507.3, -1.0), (355.8, 3.0)), "join": False,
    },
    "tmaxp3200_char": {  # T-MAX Developer, small tank, 20 C: 8 (dash-dot), 9 (short dash), 11 (long dash), 13 min (solid)
        "pdf": "tmax.pdf", "page": 25, "rect": (80.8, 69.5, 265.3, 254.0), "drawings": [16, 17, 18, 19],
        "xcal": ((80.8, -4.0), (265.3, 1.0)), "ycal": ((254.0, 0.0), (69.5, 4.0)), "join": False,
    },
})

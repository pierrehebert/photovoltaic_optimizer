// A quick and dirty box for the PZEM-004t module and it's companion ESP-01 board (no cover).

largeur = 35;
longueur = 89;
hauteur = 40;

ep=1.2;
ep_fond=0.9;

diam_trou1 = 3.2;
diam_trou2 = 2.8;
hauteur_trou = 6;

difference() {
    union() {
        linear_extrude(height=ep_fond)
        offset(delta=ep)
        square([longueur, largeur]);

        linear_extrude(height=hauteur+ep_fond)
        difference() {
            offset(delta=ep) square([longueur, largeur]);
            square([longueur, largeur]);
        }

        translate([9.5, 5, ep_fond]) cylinder(d1=diam_trou1, d2=diam_trou2, h=hauteur_trou, $fn=20);
        translate([9.5, largeur-5, ep_fond]) cylinder(d1=diam_trou1, d2=diam_trou2, h=hauteur_trou, $fn=20);
        translate([9.5+68.5, 5, ep_fond]) cylinder(d1=diam_trou1, d2=diam_trou2, h=hauteur_trou, $fn=20);
        translate([9.5+68.5, largeur-5, ep_fond]) cylinder(d1=diam_trou1, d2=diam_trou2, h=hauteur_trou, $fn=20);

        translate([40, 0, ep_fond]) cube([1, 1, hauteur]);
        translate([60.4, 0, ep_fond]) cube([1, 1, hauteur]);
        translate([40, largeur-1, ep_fond]) cube([1, 1, hauteur]);
        translate([60.4, largeur-1, ep_fond]) cube([1, 1, hauteur]);
    }

    translate([-5, (largeur-22)/2, ep_fond+4]) cube([10, 22, 7]);
}
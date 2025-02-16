//----------------------------------------------------------------------------
//  Several utility functions to modify docstring webpages while they are
//  rendered
//----------------------------------------------------------------------------

$(document).ready(function () {
    redrawConnectors()
});

window.onresize = resize;
function resize() {
    redrawConnectors()
}

function redrawConnectors() {
    $('[id^=line_]').each(function() {
      div1 = document.getElementById(this.getAttribute("node1"));
      div2 = document.getElementById(this.getAttribute("node2"));
      var rect1 = div1.getBoundingClientRect();
      var rect2 = div2.getBoundingClientRect();
      var x1 = (rect1.left+rect1.right)*0.5+window.scrollX;
      var y1 = rect1.bottom+1+window.scrollY;
      var x2 = (rect2.left+rect2.right)*0.5+window.scrollX;
      var y2 = rect2.top-1+window.scrollY;
      this.setAttribute("x1", x1);
      this.setAttribute("y1", y1);
      this.setAttribute("x2", x2);
      this.setAttribute("y2", y2);
      // this.setAttribute("viewBox",
      //                   (x1-20).toString() + " " + (y1-20).toString() + " " +
      //                   (x2+20).toString() + " " + (y2+20).toString());
    });
    $('[id^=arc_]').each(function() {
      div1 = document.getElementById(this.getAttribute("node"));
//      var pad = parseFloat(window.getComputedStyle(div1, null).getPropertyValue('padding'))
      var rr = div1.getBoundingClientRect();
      this.setAttribute("d",
                        "M " + (rr.left+window.scrollX).toString() +
                        " " + (rr.bottom+window.scrollY).toString() +
                        "m 10 0 c 5 15 15 15 20 0");
    });
}

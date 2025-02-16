//----------------------------------------------------------------------------
//  Several utility functions to modify docstring webpages while they are
//  rendered
//----------------------------------------------------------------------------

$(document).ready(function () {
    // Remove anchor header links.
    // They're used by Sphinx to create crossrefs, so we don't need them
    // $('a.headerlink').remove();
    
    // If the first child in the docstring div is a section, change its class
    // to title. This means that the docstring has a real title and we need
    // to use it.
    // This is really useful to show module docstrings.
    var first_doc_child = $('div.docstring').children(':first-child');
    if( first_doc_child.is('div.section') && $('div.title').length == 0 ) {
        first_doc_child.removeClass('section').addClass('title');
    };
    
    // Change docstring headers from h1 to h3
    // It can only be an h1 and that's the page title
    // Taken from http://forum.jquery.com/topic/how-to-replace-h1-h2
    $('div.docstring').find('div.section h1').replaceWith(function () {
        return '<h3>' + $(this).text() + '</h3>';
    });

    redrawConnectors()

});

function redrawConnectors() {
    $('[id^=line_]').each(function() {
      div1 = document.getElementById(this.getAttribute("node1"));
      div2 = document.getElementById(this.getAttribute("node2"));
      var rect1 = div1.getBoundingClientRect();
      var rect2 = div2.getBoundingClientRect();
      this.setAttribute("x1", (rect1.left+rect1.right)*0.5+window.scrollX);
      this.setAttribute("y1", rect1.bottom+1+window.scrollY);
      this.setAttribute("x2", (rect2.left+rect2.right)*0.5+window.scrollX);
      this.setAttribute("y2", rect2.top-1+window.scrollY);
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

window.onresize = resize;
function resize() {
    redrawConnectors()
}

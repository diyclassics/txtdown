# txtdown
Markup specification for plaintext corpus documents. Designed originally for use with the Plaintext Latin Library corpus.

## Quoted material
Quoted material can be expressed using Markdown's system for [blockquotes](https://daringfireball.net/projects/markdown/syntax#blockquote)

### Example

``Quamquam Ennius recte:

> Amicus certus in re incerta cernitur,

tamen haec duo levitatis et infirmitatis plerosque convincunt, aut si in bonis rebus contemnunt aut in malis deserunt.``

## Separating texts
So, for example, for the poems of Catullus, each poem can be delimited using Markdown's system for [horizontal rules](https://daringfireball.net/projects/markdown/syntax#hr). The syntax is as follows: a horizontal rule, followed by a citation number in brackets, followed by a second horizontal rule. Any content following the bracketed citation number between the horizontal rules is considered a comment. Note that, because asterisks are commonly used in plaintext documents to indicate missing lines, it is preferable (required?) to use the "hyphen"-based system for horizontal rules. Txtdown style uses five (5) hyphens for text separation.

### Example

``
-----
[1] ad Cornelium
-----
``

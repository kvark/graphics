# graphics
Mind Map of Graphics

```mermaid
  graph TD;
      Lambert --> |V-cavity distribution| OrenNayar;
      Phong --> |normal distribution| GGX;
      GGX --> |can't hit back-facing normals| VNDF;
      click VNDF "https://jcgt.org/published/0007/04/01/paper.pdf" _blank
      GGX --> |some hits are lost in scatter| Smith;
```

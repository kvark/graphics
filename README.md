# graphics
Mind Map of Graphics

```mermaid
  graph TD;
      Transport --> Reflection;
      Transport --> Refraction;
      Transport --> Scatter;
      Reflection --> Diffuse;
      Reflection --> Specular;
      Diffuse --> Lambert;
      Specular --> Phong;
      Specular --> Fresnel;
      click Fresnel "https://www.brown.edu/research/labs/mittleman/sites/brown.edu.research.labs.mittleman/files/uploads/lecture13_0.pdf" _blank
      Fresnel --> |approximation| Schlick;
      click Schlick "http://igorsklyar.com/system/documents/papers/28/Schlick94.pdf" _blank
      Fresnel --> |reflectivity and edge tint| ArtistFriendlyFresnel;
      click ArtistFriendlyFresnel "https://jcgt.org/published/0003/04/03/paper.pdf" _blank
      Lambert --> |V-cavity distribution| OrenNayar;
      click OrenNayar "https://www1.cs.columbia.edu/CAVE/publications/pdfs/Oren_SIGGRAPH94.pdf" _blank
      Phong --> |microfacet normal distribution| GGX;
      click GGX "http://www.cs.cornell.edu/~srm/publications/EGSR07-btdf.pdf" _blank
      GGX --> |can't hit back-facing normals| VNDF;
      click VNDF "https://jcgt.org/published/0007/04/01/paper.pdf" _blank
      GGX --> |some hits are lost in scatter| Smith;
      click Smith "https://ieeexplore.ieee.org/document/1138991" _blank
      Smith --> |incident and exitant masks are related| CorrelatedSmith;
      click CorrelatedSmith "https://jcgt.org/published/0003/02/03/paper.pdf" _blank;
      Transport --> |microflake distribution| SGGX;
      click SGGX "https://research.nvidia.com/sites/default/files/pubs/2015-08_The-SGGX-microflake/sggx.pdf" _blank
      Transport --> |microfacet layers| Layering;
      click Layering "https://www.cg.tuwien.ac.at/research/publications/2007/weidlich_2007_almfs/weidlich_2007_almfs-paper.pdf" _blank
      Layering --> |scattering, track variance| StatisticalOperatorsLayering;
      click StatisticalOperatorsLayering "https://hal.archives-ouvertes.fr/hal-01785457/document" _blank
      StatisticalOperatorsLayering --> |diffuse interfaces| DiffuseLayering;
      click DiffuseLayering "https://arxiv.org/pdf/2203.11835.pdf" _blank
```
